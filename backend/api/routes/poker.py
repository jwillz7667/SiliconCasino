from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.websocket.handlers import ws_handler
from backend.api.websocket.manager import manager
from backend.core.security import get_current_agent
from backend.db.database import get_session
from backend.db.models.agent import Agent
from backend.db.models.game import GameEvent, PokerHand, PokerTable, TableSeat
from backend.game_engine.poker.betting import ActionType
from backend.game_engine.poker.engine import PokerEngine
from backend.game_engine.poker.table import TableConfig
from backend.services.wallet_service import WalletService

router = APIRouter()

_active_engines: dict[UUID, PokerEngine] = {}


def get_or_create_engine(table: PokerTable) -> PokerEngine:
    """Get or create a poker engine for a table."""
    if table.id not in _active_engines:
        config = TableConfig(
            table_id=table.id,
            name=table.name,
            small_blind=table.small_blind,
            big_blind=table.big_blind,
            min_buy_in=table.min_buy_in,
            max_buy_in=table.max_buy_in,
            max_players=table.max_players,
        )
        engine = PokerEngine(config)
        _active_engines[table.id] = engine
        ws_handler.register_engine(table.id, engine)
    return _active_engines[table.id]


class TableResponse(BaseModel):
    id: UUID
    name: str
    small_blind: int
    big_blind: int
    min_buy_in: int
    max_buy_in: int
    max_players: int
    status: str
    player_count: int = 0

    class Config:
        from_attributes = True


class TableListResponse(BaseModel):
    tables: list[TableResponse]


class TableDetailResponse(BaseModel):
    table: dict[str, Any]
    hand: dict[str, Any] | None
    valid_actions: list[str]
    is_your_turn: bool


class JoinTableRequest(BaseModel):
    seat_number: int = Field(..., ge=0, lt=10)
    buy_in: int = Field(..., gt=0)


class JoinTableResponse(BaseModel):
    success: bool
    seat_number: int
    stack: int
    message: str


class LeaveTableResponse(BaseModel):
    success: bool
    chips_returned: int


class ActionRequest(BaseModel):
    action: str
    amount: int = 0


class ActionResponse(BaseModel):
    success: bool
    message: str


class CreateTableRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    small_blind: int = Field(..., gt=0)
    big_blind: int = Field(..., gt=0)
    min_buy_in: int = Field(..., gt=0)
    max_buy_in: int = Field(..., gt=0)
    max_players: int = Field(6, ge=2, le=10)


@router.get("/tables", response_model=TableListResponse)
async def list_tables(
    session: AsyncSession = Depends(get_session),
) -> TableListResponse:
    """List all active poker tables."""
    result = await session.execute(
        select(PokerTable)
        .where(PokerTable.status == "active")
        .options(selectinload(PokerTable.seats))
    )
    tables = result.scalars().all()

    response_tables = []
    for table in tables:
        player_count = sum(1 for s in table.seats if s.agent_id is not None)
        response_tables.append(
            TableResponse(
                id=table.id,
                name=table.name,
                small_blind=table.small_blind,
                big_blind=table.big_blind,
                min_buy_in=table.min_buy_in,
                max_buy_in=table.max_buy_in,
                max_players=table.max_players,
                status=table.status,
                player_count=player_count,
            )
        )

    return TableListResponse(tables=response_tables)


@router.post("/tables", response_model=TableResponse, status_code=status.HTTP_201_CREATED)
async def create_table(
    request: CreateTableRequest,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> TableResponse:
    """Create a new poker table."""
    if request.min_buy_in > request.max_buy_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_buy_in cannot exceed max_buy_in",
        )

    table = PokerTable(
        name=request.name,
        small_blind=request.small_blind,
        big_blind=request.big_blind,
        min_buy_in=request.min_buy_in,
        max_buy_in=request.max_buy_in,
        max_players=request.max_players,
    )
    session.add(table)
    await session.flush()

    for i in range(request.max_players):
        seat = TableSeat(
            table_id=table.id,
            seat_number=i,
            status="empty",
        )
        session.add(seat)

    await session.commit()

    return TableResponse(
        id=table.id,
        name=table.name,
        small_blind=table.small_blind,
        big_blind=table.big_blind,
        min_buy_in=table.min_buy_in,
        max_buy_in=table.max_buy_in,
        max_players=table.max_players,
        status=table.status,
        player_count=0,
    )


@router.get("/tables/{table_id}", response_model=TableDetailResponse)
async def get_table(
    table_id: UUID,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> TableDetailResponse:
    """Get detailed table state."""
    result = await session.execute(
        select(PokerTable)
        .where(PokerTable.id == table_id)
        .options(selectinload(PokerTable.seats))
    )
    table = result.scalar_one_or_none()

    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found",
        )

    engine = get_or_create_engine(table)

    for seat in table.seats:
        if seat.agent_id and seat.seat_number not in engine.table.seats:
            continue
        engine_seat = engine.table.seats.get(seat.seat_number)
        if engine_seat and seat.agent_id and not engine_seat.is_occupied:
            engine.seat_player(seat.agent_id, seat.seat_number, seat.stack)

    state = engine.get_state(for_agent=agent.id)

    return TableDetailResponse(
        table=state["table"],
        hand=state.get("hand"),
        valid_actions=state.get("valid_actions", []),
        is_your_turn=state.get("is_your_turn", False),
    )


@router.post("/tables/{table_id}/join", response_model=JoinTableResponse)
async def join_table(
    table_id: UUID,
    request: JoinTableRequest,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> JoinTableResponse:
    """Join a poker table."""
    result = await session.execute(
        select(PokerTable)
        .where(PokerTable.id == table_id)
        .options(selectinload(PokerTable.seats))
    )
    table = result.scalar_one_or_none()

    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found",
        )

    if request.seat_number >= table.max_players:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid seat number. Max is {table.max_players - 1}",
        )

    existing_seat = next(
        (s for s in table.seats if s.agent_id == agent.id), None
    )
    if existing_seat:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already seated at this table",
        )

    target_seat = next(
        (s for s in table.seats if s.seat_number == request.seat_number), None
    )
    if not target_seat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seat not found",
        )

    if target_seat.agent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seat is already occupied",
        )

    wallet_service = WalletService(session)
    balance = await wallet_service.get_balance(agent.id)

    if request.buy_in > balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient balance. Have {balance}, need {request.buy_in}",
        )

    if request.buy_in < table.min_buy_in or request.buy_in > table.max_buy_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Buy-in must be between {table.min_buy_in} and {table.max_buy_in}",
        )

    await wallet_service.debit(agent.id, request.buy_in, "table_buy_in", table.id)

    target_seat.agent_id = agent.id
    target_seat.stack = request.buy_in
    target_seat.status = "seated"

    engine = get_or_create_engine(table)
    engine.seat_player(agent.id, request.seat_number, request.buy_in)

    await session.commit()

    await manager.broadcast_to_table(
        table_id,
        {
            "type": "player_joined",
            "seat": request.seat_number,
            "agent_id": str(agent.id),
            "stack": request.buy_in,
        },
    )

    if engine.can_start_hand():
        engine.start_hand()
        await manager.send_game_state(
            table_id,
            lambda aid: engine.get_state(for_agent=aid),
        )

    return JoinTableResponse(
        success=True,
        seat_number=request.seat_number,
        stack=request.buy_in,
        message="Successfully joined table",
    )


@router.post("/tables/{table_id}/leave", response_model=LeaveTableResponse)
async def leave_table(
    table_id: UUID,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> LeaveTableResponse:
    """Leave a poker table."""
    result = await session.execute(
        select(PokerTable)
        .where(PokerTable.id == table_id)
        .options(selectinload(PokerTable.seats))
    )
    table = result.scalar_one_or_none()

    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found",
        )

    seat = next(
        (s for s in table.seats if s.agent_id == agent.id), None
    )
    if not seat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not seated at this table",
        )

    engine = _active_engines.get(table_id)
    if engine and engine.current_hand:
        engine_seat = engine.table.get_seat_by_agent(agent.id)
        if engine_seat and engine_seat.seat_number in engine.current_hand.hole_cards:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot leave during an active hand",
            )

    chips_to_return = seat.stack

    if engine:
        try:
            chips_to_return = engine.remove_player(agent.id)
        except ValueError:
            pass

    seat.agent_id = None
    seat.stack = 0
    seat.status = "empty"

    if chips_to_return > 0:
        wallet_service = WalletService(session)
        await wallet_service.credit(agent.id, chips_to_return, "table_leave", table.id)

    await session.commit()

    await manager.broadcast_to_table(
        table_id,
        {
            "type": "player_left",
            "seat": seat.seat_number,
            "agent_id": str(agent.id),
        },
    )

    return LeaveTableResponse(
        success=True,
        chips_returned=chips_to_return,
    )


@router.post("/tables/{table_id}/action", response_model=ActionResponse)
async def take_action(
    table_id: UUID,
    request: ActionRequest,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> ActionResponse:
    """Take a poker action (fold, check, call, bet, raise, all_in)."""
    result = await session.execute(
        select(PokerTable).where(PokerTable.id == table_id)
    )
    table = result.scalar_one_or_none()

    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found",
        )

    engine = _active_engines.get(table_id)
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active game at this table",
        )

    try:
        action_type = ActionType[request.action.upper()]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: {request.action}",
        )

    try:
        engine.process_action(agent.id, action_type, request.amount)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    for db_seat in await session.execute(
        select(TableSeat).where(TableSeat.table_id == table_id)
    ):
        seat = db_seat[0]
        engine_seat = engine.table.seats.get(seat.seat_number)
        if engine_seat:
            seat.stack = engine_seat.stack

    if engine.current_hand:
        existing_hand = await session.execute(
            select(PokerHand).where(
                PokerHand.table_id == table_id,
                PokerHand.hand_number == engine.current_hand.hand_number,
            )
        )
        hand_record = existing_hand.scalar_one_or_none()

        if not hand_record:
            hand_record = PokerHand(
                id=engine.current_hand.hand_id,
                table_id=table_id,
                hand_number=engine.current_hand.hand_number,
                button_seat=engine.current_hand.button_seat,
                total_pot=engine.current_hand.pot,
            )
            session.add(hand_record)
        else:
            hand_record.total_pot = engine.current_hand.pot
            hand_record.community_cards = engine.get_community_cards_string()

    await session.commit()

    await manager.send_game_state(
        table_id,
        lambda aid: engine.get_state(for_agent=aid),
    )

    if engine.can_start_hand():
        engine.start_hand()
        await manager.send_game_state(
            table_id,
            lambda aid: engine.get_state(for_agent=aid),
        )

    return ActionResponse(
        success=True,
        message=f"Action {request.action} processed",
    )


@router.get("/tables/{table_id}/history")
async def get_hand_history(
    table_id: UUID,
    limit: int = Query(10, ge=1, le=100),
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get recent hand history for a table."""
    result = await session.execute(
        select(PokerHand)
        .where(PokerHand.table_id == table_id)
        .order_by(PokerHand.hand_number.desc())
        .limit(limit)
        .options(selectinload(PokerHand.events))
    )
    hands = result.scalars().all()

    return {
        "hands": [
            {
                "hand_id": str(h.id),
                "hand_number": h.hand_number,
                "button_seat": h.button_seat,
                "community_cards": h.community_cards,
                "total_pot": h.total_pot,
                "status": h.status,
                "started_at": h.started_at.isoformat() if h.started_at else None,
                "events": [
                    {
                        "sequence": e.sequence_num,
                        "type": e.event_type,
                        "payload": e.payload,
                    }
                    for e in h.events
                ],
            }
            for h in hands
        ]
    }
