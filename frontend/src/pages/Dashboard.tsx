import { useState, useEffect } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer, Cell
} from 'recharts';
import { AlertTriangle, Clock, CalendarCheck, Zap, Database, Server, Settings } from 'lucide-react';
import { api } from '../services/api';

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);
  const [pipelineLoading, setPipelineLoading] = useState(false);

  const fetchDashboardData = async () => {
    try {
      const res = await api.getAnalytics();
      setData(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const runFullPipeline = async () => {
    setPipelineLoading(true);
    try {
      await api.generateData();
      await api.loadData("hyderabad");
      await api.calculatePriority();
      await api.getCoordinationGroups();
      await api.getBlockWindows();
      await api.runBaseline();
      await api.runOptimizer();
      await fetchDashboardData();
    } catch (e) {
      console.error(e);
      alert('Pipeline failed. See console.');
    } finally {
      setPipelineLoading(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-full"><div className="animate-pulse flex items-center gap-2"><Server className="w-5 h-5 text-sky-400" /><span>Connecting to HYDRA Core...</span></div></div>;
  }

  const hasData = !!data?.kpi?.total_tasks;

  if (!hasData && !loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[70vh] text-center max-w-lg mx-auto">
        <div className="w-20 h-20 bg-slate-800 rounded-full flex items-center justify-center mb-6 border border-slate-700 shadow-xl">
          <Database className="w-10 h-10 text-sky-400" />
        </div>
        <h2 className="text-2xl font-bold mb-2">No Data Loaded</h2>
        <p className="text-slate-400 mb-8">
          The system needs track, signal, and traction maintenance data to generate an optimized block plan.
        </p>
        <button 
          onClick={runFullPipeline}
          disabled={pipelineLoading}
          className="bg-sky-500 hover:bg-sky-400 text-slate-900 font-semibold py-3 px-6 rounded-lg transition-all flex items-center gap-2 shadow-[0_0_15px_rgba(56,189,248,0.4)] disabled:opacity-50"
        >
          {pipelineLoading ? (
             <><Settings className="w-5 h-5 animate-spin" /> Running Pipeline...</>
          ) : (
            <><Zap className="w-5 h-5" /> Run Full Demo Pipeline</>
          )}
        </button>
      </div>
    );
  }

  const { kpi, comparison, priority_summary } = data;

  const comparisonData = [
    { name: 'Total Blocks', Baseline: comparison.baseline?.total_blocks || 0, HYDRA: comparison.optimized?.total_blocks || 0 },
    { name: 'Block Hours', Baseline: comparison.baseline?.total_block_hours || 0, HYDRA: comparison.optimized?.total_block_hours || 0 },
  ];

  const priorityData = [
    { name: 'Critical', count: priority_summary?.CRITICAL || 0, fill: '#ef4444' },
    { name: 'High', count: priority_summary?.HIGH || 0, fill: '#f97316' },
    { name: 'Medium', count: priority_summary?.MEDIUM || 0, fill: '#eab308' },
    { name: 'Low', count: priority_summary?.LOW || 0, fill: '#22c55e' },
  ];

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-1">Executive Dashboard</h1>
          <p className="text-slate-400">Weekly Maintenance Operations Overview</p>
        </div>
        <button 
          onClick={runFullPipeline}
          disabled={pipelineLoading}
          className="bg-slate-800 hover:bg-slate-700 border border-slate-600 text-white font-medium py-2 px-4 rounded-md transition-colors flex items-center gap-2 text-sm disabled:opacity-50"
        >
          {pipelineLoading ? <Settings className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4 text-sky-400" />}
          {pipelineLoading ? 'Running...' : 'Re-run Pipeline'}
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-800 border border-slate-700 p-5 rounded-xl shadow-lg relative overflow-hidden group">
          <div className="absolute -right-6 -top-6 w-24 h-24 bg-red-500/10 rounded-full blur-xl group-hover:bg-red-500/20 transition-all"></div>
          <div className="flex justify-between items-start mb-4 relative">
            <div className="p-2 bg-red-500/20 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-red-500" />
            </div>
          </div>
          <h3 className="text-slate-400 font-medium text-sm">Critical Tasks</h3>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white">{kpi.critical_tasks}</span>
            <span className="text-xs text-slate-500">pending</span>
          </div>
        </div>

        <div className="bg-slate-800 border border-slate-700 p-5 rounded-xl shadow-lg relative overflow-hidden group">
          <div className="absolute -right-6 -top-6 w-24 h-24 bg-orange-500/10 rounded-full blur-xl group-hover:bg-orange-500/20 transition-all"></div>
          <div className="flex justify-between items-start mb-4 relative">
            <div className="p-2 bg-orange-500/20 rounded-lg">
              <Clock className="w-5 h-5 text-orange-500" />
            </div>
          </div>
          <h3 className="text-slate-400 font-medium text-sm">Overdue Remaining</h3>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white">{kpi.overdue_remaining}</span>
            <span className="text-xs text-slate-500">of {kpi.overdue_tasks}</span>
          </div>
        </div>

        <div className="bg-slate-800 border border-slate-700 p-5 rounded-xl shadow-lg relative overflow-hidden group">
          <div className="absolute -right-6 -top-6 w-24 h-24 bg-sky-500/10 rounded-full blur-xl group-hover:bg-sky-500/20 transition-all"></div>
          <div className="flex justify-between items-start mb-4 relative">
            <div className="p-2 bg-sky-500/20 rounded-lg">
              <CalendarCheck className="w-5 h-5 text-sky-400" />
            </div>
          </div>
          <h3 className="text-slate-400 font-medium text-sm">Scheduled Blocks</h3>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white">{kpi.scheduled_blocks}</span>
            <span className="text-sm font-medium text-emerald-400 ml-2">-{Math.round((1 - comparison.optimized?.total_blocks / Math.max(comparison.baseline?.total_blocks, 1)) * 100)}%</span>
          </div>
        </div>

        <div className="bg-slate-800 border border-slate-700 p-5 rounded-xl shadow-lg relative overflow-hidden group">
          <div className="absolute -right-6 -top-6 w-24 h-24 bg-emerald-500/10 rounded-full blur-xl group-hover:bg-emerald-500/20 transition-all"></div>
          <div className="flex justify-between items-start mb-4 relative">
            <div className="p-2 bg-emerald-500/20 rounded-lg">
              <Zap className="w-5 h-5 text-emerald-500" />
            </div>
          </div>
          <h3 className="text-slate-400 font-medium text-sm">Bundled Tasks</h3>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white">{kpi.bundled_tasks}</span>
            <span className="text-xs text-slate-500">multi-dept</span>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-800 border border-slate-700 p-5 rounded-xl shadow-lg">
          <h3 className="text-lg font-semibold mb-6 flex items-center gap-2">
            <span className="w-1.5 h-6 bg-sky-500 rounded-full inline-block"></span>
            Optimization Impact
          </h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={comparisonData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                <XAxis dataKey="name" stroke="#94a3b8" tick={{fill: '#94a3b8'}} />
                <YAxis stroke="#94a3b8" tick={{fill: '#94a3b8'}} />
                <RechartsTooltip 
                  cursor={{fill: '#334155', opacity: 0.4}}
                  contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc' }}
                />
                <Legend wrapperStyle={{ paddingTop: '20px' }} />
                <Bar dataKey="Baseline" fill="#475569" radius={[4, 4, 0, 0]} name="Baseline (Decentralized)" />
                <Bar dataKey="HYDRA" fill="#0ea5e9" radius={[4, 4, 0, 0]} name="HYDRA Optimized" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-4 p-3 bg-sky-500/10 border border-sky-500/20 rounded-lg">
            <p className="text-sm text-sky-400 flex items-center gap-2">
              <Zap className="w-4 h-4" /> 
              <strong>{Math.round((comparison.baseline?.total_block_hours - comparison.optimized?.total_block_hours))} hours</strong> of track time saved compared to manual decentralized planning.
            </p>
          </div>
        </div>

        <div className="bg-slate-800 border border-slate-700 p-5 rounded-xl shadow-lg">
          <h3 className="text-lg font-semibold mb-6 flex items-center gap-2">
            <span className="w-1.5 h-6 bg-amber-500 rounded-full inline-block"></span>
            Task Priority Distribution
          </h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={priorityData} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
                <XAxis type="number" stroke="#94a3b8" tick={{fill: '#94a3b8'}} />
                <YAxis dataKey="name" type="category" stroke="#94a3b8" tick={{fill: '#94a3b8'}} />
                <RechartsTooltip 
                  cursor={{fill: '#334155', opacity: 0.4}}
                  contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc' }}
                />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {
                    priorityData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))
                  }
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
