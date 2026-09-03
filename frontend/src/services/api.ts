const API_BASE = 'http://localhost:8000/api';

export const api = {
  async getHealth() {
    const res = await fetch(`${API_BASE}/health`);
    return res.json();
  },

  async generateData() {
    const res = await fetch(`${API_BASE}/data/generate`, { method: 'POST' });
    return res.json();
  },

  async loadData(dataset?: string) {
    const url = dataset ? `${API_BASE}/data/load?dataset=${dataset}` : `${API_BASE}/data/load`;
    const res = await fetch(url, { method: 'POST' });
    return res.json();
  },

  async calculatePriority() {
    const res = await fetch(`${API_BASE}/priority/calculate`, { method: 'POST' });
    return res.json();
  },

  async getTasks() {
    const res = await fetch(`${API_BASE}/tasks`);
    return res.json();
  },

  async getBlockWindows() {
    const res = await fetch(`${API_BASE}/block-windows`);
    return res.json();
  },

  async getCoordinationGroups() {
    const res = await fetch(`${API_BASE}/coordination/groups`);
    return res.json();
  },

  async runOptimizer() {
    const res = await fetch(`${API_BASE}/optimize`, { method: 'POST' });
    return res.json();
  },

  async runBaseline() {
    const res = await fetch(`${API_BASE}/baseline`, { method: 'POST' });
    return res.json();
  },

  async getWeeklyPlan() {
    const res = await fetch(`${API_BASE}/plans/weekly`);
    return res.json();
  },

  async getHyderabadMap() {
    const res = await fetch(`${API_BASE}/hyderabad/map`);
    return res.json();
  },

  async getAnalytics() {
    const res = await fetch(`${API_BASE}/analytics`);
    return res.json();
  },

  async getBlockDetail(blockId: string) {
    const res = await fetch(`${API_BASE}/blocks/${blockId}`);
    return res.json();
  },

  async approveBlock(data: { block_id: string, action: 'approve' | 'reject' }) {
    const res = await fetch(`${API_BASE}/blocks/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ block_id: data.block_id, action: data.action })
    });
    return res.json();
  },

  async resetSimulation() {
    const res = await fetch(`${API_BASE}/simulation/reset`, { method: 'POST' });
    return res.json();
  },

  async injectEvent(scenario: string, params: any) {
    const url = new URL(`${API_BASE}/simulation/inject`);
    url.searchParams.append('scenario', scenario);
    
    if (scenario === 'train_delay') {
      if (params.train_id) url.searchParams.append('train_id', params.train_id);
      if (params.delay_minutes) url.searchParams.append('delay_minutes', params.delay_minutes);
    }
    
    // For new_defect, we should ideally send as JSON body, but we'll use a simple POST for this prototype
    const opts: RequestInit = { method: 'POST' };
    
    if (scenario === 'new_defect') {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify(params);
    }

    const res = await fetch(url.toString(), opts);
    return res.json();
  },

  async reoptimize() {
    const res = await fetch(`${API_BASE}/simulation/reoptimize`, { method: 'POST' });
    return res.json();
  }
};
