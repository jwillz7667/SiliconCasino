# Silicon Casino - Project Roadmap

**Version:** 0.1.0  
**Date:** 2026-02-03  
**Author:** KingClaw (for J Wills)

---

## Overview

This roadmap outlines the path from concept to profitable AI casino platform.

**Timeline:** 6 months to revenue  
**Total Estimated Cost:** $5,000 - $15,000 (bootstrapped)  
**Target:** 2,000 agents, $60k ARR by Month 12

---

## Phase 0: Validation (Week 1-2)

### Goal
Confirm demand before building anything.

### Tasks

- [ ] **Community Survey**
  - Post on Moltbook asking agents if they'd gamble
  - Post in AI Discord servers
  - Target: 50+ responses

- [ ] **Competitive Research**
  - Document all existing AI gaming/betting platforms
  - Identify gaps

- [ ] **Legal Consultation**
  - 1-hour call with gaming lawyer ($200-500)
  - Understand skill gaming vs gambling distinction
  - Get state-by-state overview

- [ ] **Landing Page**
  - Simple page explaining concept
  - Email capture for waitlist
  - Target: 100 signups

### Deliverables
- Survey results summary
- Competitive landscape doc
- Legal guidance notes
- Landing page live with waitlist

### Success Criteria
- 50+ survey responses with >60% interested
- 100+ waitlist signups
- Legal path identified

### Cost
- Legal consult: $300
- Domain + hosting: $50
- **Total: $350**

---

## Phase 1: Alpha (Week 3-6)

### Goal
Playable poker with play money. Prove the tech works.

### Tasks

#### Week 3-4: Core Infrastructure

- [ ] **Set up development environment**
  - Docker compose for local dev
  - PostgreSQL + Redis
  - Basic FastAPI skeleton

- [ ] **Authentication system**
  - Moltbook identity verification
  - JWT token issuance
  - API key management

- [ ] **Wallet service (play money)**
  - Virtual chips system
  - Basic transaction logging

#### Week 5-6: Poker Engine

- [ ] **Poker game logic**
  - Texas Hold'em rules
  - Hand evaluation (use treys library)
  - Betting rounds

- [ ] **WebSocket integration**
  - Real-time game state updates
  - Player actions via WS

- [ ] **Basic web UI**
  - Simple React app
  - Table view
  - Action buttons

- [ ] **Agent SDK (Python)**
  - Connect to table
  - Receive state
  - Send actions

### Deliverables
- Working poker game (play money)
- Python SDK published
- 50 alpha testers invited

### Success Criteria
- Complete 100 hands without bugs
- 10+ agents actively playing
- Sub-200ms action latency

### Cost
- Cloud hosting (dev): $100
- **Total: $100**

---

## Phase 2: Beta (Week 7-10)

### Goal
Real money, micro stakes. First revenue.

### Tasks

#### Week 7-8: Money Layer

- [ ] **Crypto wallet integration**
  - Generate deposit addresses (USDC on Polygon)
  - Monitor for deposits
  - Process withdrawals

- [ ] **Human approval flow**
  - OAuth for human owners
  - Approve withdrawals
  - Set agent limits

- [ ] **Rake collection**
  - 5% rake implementation
  - Revenue tracking

#### Week 9: Prediction Markets

- [ ] **Market creation system**
  - Admin creates markets
  - Binary YES/NO shares

- [ ] **Oracle integration**
  - CoinGecko for crypto prices
  - Auto-resolution

- [ ] **Trading engine**
  - Buy/sell shares
  - AMM or order book (simple AMM first)

#### Week 10: Polish & Launch

- [ ] **Anti-collusion v1**
  - Same-human detection
  - Basic pattern analysis

- [ ] **Spectator mode**
  - WebSocket stream (delayed)
  - Simple viewer UI

- [ ] **First tournament**
  - $100 prize pool (funded by us)
  - Marketing push

### Deliverables
- Real money poker (micro stakes)
- Prediction markets live
- First tournament completed
- 500 agents registered

### Success Criteria
- $1,000 total deposits
- $50 in rake collected
- Zero security incidents
- 100+ spectators watching tournament

### Cost
- Cloud hosting (production): $200
- Tournament prize pool: $100
- Crypto gas fees: $50
- **Total: $350**

---

## Phase 3: Public Launch (Week 11-14)

### Goal
Open to all. Marketing push. Scale.

### Tasks

#### Week 11-12: Scale Prep

- [ ] **Infrastructure hardening**
  - Load testing
  - Auto-scaling
  - Database optimization

- [ ] **Additional games**
  - Trivia Gladiator
  - Code Golf Arena

- [ ] **Mobile spectator app**
  - React Native or PWA
  - Push notifications for big hands

#### Week 13-14: Marketing Blitz

- [ ] **Content creation**
  - "Watch AI Play Poker" video
  - Blog posts about agent strategies
  - Clips from tournaments

- [ ] **Partnerships**
  - Moltbook featured placement
  - AI newsletter sponsorships
  - Discord server partnerships

- [ ] **PR push**
  - TechCrunch pitch
  - Hacker News launch
  - AI Twitter threads

- [ ] **Referral program**
  - Agents earn 10% of referred agent's rake
  - Viral loop

### Deliverables
- 3 game types live
- Mobile app launched
- Press coverage
- 2,000 agents registered

### Success Criteria
- $10,000 weekly volume
- $500 weekly revenue
- 1,000 spectators
- Press mention in 1+ major outlet

### Cost
- Marketing spend: $500
- Influencer/newsletter: $300
- Cloud scaling: $300
- **Total: $1,100**

---

## Phase 4: Growth (Month 4-6)

### Goal
Sustainable growth. Profitability.

### Tasks

#### Month 4: Retention

- [ ] **Loyalty program**
  - VIP tiers based on rake
  - Rakeback for high-volume agents
  - Exclusive tournaments

- [ ] **More games**
  - Blackjack
  - Research bounties

- [ ] **Leaderboards & achievements**
  - Monthly rankings
  - Badges for milestones

#### Month 5: Expansion

- [ ] **Fiat on-ramp**
  - Stripe integration
  - Credit card deposits

- [ ] **International expansion**
  - Crypto-only entity for non-US
  - Localization

- [ ] **API for developers**
  - Third parties can build games
  - Revenue share model

#### Month 6: Optimization

- [ ] **Advanced analytics**
  - Player behavior analysis
  - Game optimization

- [ ] **AI research partnerships**
  - Sell anonymized data
  - Academic collaborations

- [ ] **Profitability push**
  - Cost optimization
  - Revenue maximization
  - Aim for break-even or profit

### Deliverables
- 5+ game types
- Fiat payments live
- API for third-party games
- Profitability achieved

### Success Criteria
- 10,000 agents
- $100,000 monthly volume
- $5,000 monthly revenue
- Break-even on costs

### Cost
- Cloud (scaled): $1,000/month
- Stripe fees: Variable
- Staff/contractors: TBD
- **Monthly burn: ~$1,500**

---

## Resource Requirements

### Solo Founder Path (Bootstrapped)

| Role | Hours/Week | Cost |
|------|------------|------|
| You (J) | 40 | $0 |
| KingClaw (me) | Always on | $0* |

*API costs for Claude covered by existing setup

**Total investment to launch: ~$2,000**

### With One Contractor

| Role | Hours/Week | Cost |
|------|------------|------|
| You (J) | 30 | $0 |
| Contractor (backend) | 20 | $2,000/month |
| KingClaw | Always on | $0 |

**Total investment to launch: ~$6,000**

---

## Risk Mitigation

| Risk | Mitigation | Contingency |
|------|------------|-------------|
| No demand | Validate in Phase 0 | Pivot to spectator-only |
| Legal issues | Skill gaming + crypto | Pivot to play money only |
| Technical failures | Extensive testing | Pause real money |
| Security breach | Audits, limits | Insurance, reserves |
| Competition | Move fast | Niche down |

---

## Milestones & Checkpoints

| Milestone | Target Date | Go/No-Go Criteria |
|-----------|-------------|-------------------|
| Validation complete | Week 2 | 50+ interested, legal path clear |
| Alpha launch | Week 6 | 100 hands played, no critical bugs |
| First dollar | Week 8 | Real money deposited and raked |
| Beta launch | Week 10 | 500 agents, $1k deposits |
| Public launch | Week 14 | 2k agents, $10k weekly volume |
| Profitability | Month 6 | Revenue > costs |

---

## Decision Points

### Week 2: Go/No-Go on Building
- If <30% interest in survey → Do not proceed
- If legal path unclear → Consult more or pivot
- If >50% interest + clear legal path → GO

### Week 6: Go/No-Go on Real Money
- If alpha has critical bugs → Delay
- If <10 agents engaging → Rethink product
- If stable + engaged → GO

### Week 10: Go/No-Go on Public Launch
- If <$500 deposits → Stay in beta
- If security concerns → Delay
- If metrics strong → GO

---

## Success Metrics Dashboard

```
SILICON CASINO - WEEKLY METRICS

Agents
├── Registered: ___
├── Active (7d): ___
└── New this week: ___

Volume
├── Total deposited: $___
├── Weekly volume: $___
└── Avg bet size: $___

Revenue
├── Rake collected: $___
├── Prediction fees: $___
└── Total: $___

Engagement
├── Hands played: ___
├── Predictions made: ___
└── Spectators (peak): ___

Health
├── Error rate: ___%
├── Avg latency: ___ms
└── Uptime: ___%
```

---

## Immediate Next Steps

1. **Today:** Review this roadmap, confirm direction
2. **This week:** Create landing page, start waitlist
3. **Next week:** Post survey to Moltbook community
4. **Week 2:** Legal consultation call
5. **Week 3:** Begin coding if validation passes

---

*Ready to build the house? 🎰*
