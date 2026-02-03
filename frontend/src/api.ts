const BASE_URL = "/api";

async function fetchWithAuth(
  endpoint: string,
  options: RequestInit = {},
  token?: string | null
): Promise<Response> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response;
}

export const api = {
  async register(displayName: string) {
    const res = await fetchWithAuth("/auth/register", {
      method: "POST",
      body: JSON.stringify({ display_name: displayName }),
    });
    return res.json();
  },

  async getToken(apiKey: string) {
    const res = await fetchWithAuth("/auth/token", {
      method: "POST",
      body: JSON.stringify({ api_key: apiKey }),
    });
    return res.json();
  },

  async getMe(token: string) {
    const res = await fetchWithAuth("/auth/me", {}, token);
    return res.json();
  },

  async getBalance(token: string) {
    const res = await fetchWithAuth("/wallet", {}, token);
    return res.json();
  },

  async creditChips(token: string, amount: number) {
    const res = await fetchWithAuth(
      "/wallet/credit",
      {
        method: "POST",
        body: JSON.stringify({ amount }),
      },
      token
    );
    return res.json();
  },

  async listTables(token: string) {
    const res = await fetchWithAuth("/poker/tables", {}, token);
    return res.json();
  },

  async createTable(
    token: string,
    data: {
      name: string;
      small_blind: number;
      big_blind: number;
      min_buy_in: number;
      max_buy_in: number;
      max_players?: number;
    }
  ) {
    const res = await fetchWithAuth(
      "/poker/tables",
      {
        method: "POST",
        body: JSON.stringify(data),
      },
      token
    );
    return res.json();
  },

  async getTable(token: string, tableId: string) {
    const res = await fetchWithAuth(`/poker/tables/${tableId}`, {}, token);
    return res.json();
  },

  async joinTable(
    token: string,
    tableId: string,
    seatNumber: number,
    buyIn: number
  ) {
    const res = await fetchWithAuth(
      `/poker/tables/${tableId}/join`,
      {
        method: "POST",
        body: JSON.stringify({ seat_number: seatNumber, buy_in: buyIn }),
      },
      token
    );
    return res.json();
  },

  async leaveTable(token: string, tableId: string) {
    const res = await fetchWithAuth(
      `/poker/tables/${tableId}/leave`,
      { method: "POST" },
      token
    );
    return res.json();
  },

  async takeAction(
    token: string,
    tableId: string,
    action: string,
    amount: number = 0
  ) {
    const res = await fetchWithAuth(
      `/poker/tables/${tableId}/action`,
      {
        method: "POST",
        body: JSON.stringify({ action, amount }),
      },
      token
    );
    return res.json();
  },
};
