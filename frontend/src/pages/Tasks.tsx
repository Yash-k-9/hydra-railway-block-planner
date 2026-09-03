import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { ShieldAlert, AlertTriangle, AlertCircle, Info, Search } from 'lucide-react';
import { clsx } from 'clsx';

export default function Tasks() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('ALL');
  const [search, setSearch] = useState('');

  useEffect(() => {
    const fetchTasks = async () => {
      try {
        const res = await api.getTasks();
        // Sort by priority score descending
        const sorted = res.tasks.sort((a: any, b: any) => b.priority_score - a.priority_score);
        setTasks(sorted);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchTasks();
  }, []);

  const getPriorityBadge = (level: string, score: number) => {
    switch (level) {
      case 'CRITICAL': return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-red-500/20 text-red-400 border border-red-500/30"><ShieldAlert className="w-3 h-3" /> {score} CRITICAL</span>;
      case 'HIGH': return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-orange-500/20 text-orange-400 border border-orange-500/30"><AlertTriangle className="w-3 h-3" /> {score} HIGH</span>;
      case 'MEDIUM': return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30"><AlertCircle className="w-3 h-3" /> {score} MEDIUM</span>;
      case 'LOW': return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"><Info className="w-3 h-3" /> {score} LOW</span>;
      default: return <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-slate-700 text-slate-300">{score} UNRATED</span>;
    }
  };

  const getDeptColor = (dept: string) => {
    switch (dept) {
      case 'ENGINEERING': return 'text-sky-400 bg-sky-400/10 border-sky-400/20';
      case 'SIGNALLING': return 'text-purple-400 bg-purple-400/10 border-purple-400/20';
      case 'TRACTION': return 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20';
      default: return 'text-slate-400 bg-slate-800 border-slate-700';
    }
  };

  const filteredTasks = tasks.filter(t => {
    if (filter !== 'ALL' && t.priority_level !== filter) return false;
    if (search && !t.task_id.toLowerCase().includes(search.toLowerCase()) && 
        !t.description.toLowerCase().includes(search.toLowerCase()) &&
        !t.corridor_id.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  if (loading) {
    return <div className="animate-pulse h-full bg-slate-800 rounded-xl p-8">Loading tasks...</div>;
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white mb-1">Priority Queue</h1>
        <p className="text-slate-400">Unified view of all departmental maintenance requirements sorted by algorithmic priority.</p>
      </div>

      <div className="flex flex-col sm:flex-row justify-between gap-4 bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm">
        <div className="flex flex-wrap gap-2">
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(level => (
            <button
              key={level}
              onClick={() => setFilter(level)}
              className={clsx(
                "px-4 py-1.5 rounded-full text-sm font-medium transition-colors border",
                filter === level 
                  ? "bg-slate-700 border-slate-500 text-white shadow-sm" 
                  : "bg-transparent border-slate-700 text-slate-400 hover:text-white hover:bg-slate-700/50"
              )}
            >
              {level}
            </button>
          ))}
        </div>
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input 
            type="text" 
            placeholder="Search tasks..." 
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-4 py-1.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500 w-full sm:w-64 transition-shadow"
          />
        </div>
      </div>

      <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden shadow-lg">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-900/50 border-b border-slate-700 text-slate-400 text-xs uppercase tracking-wider">
                <th className="p-4 font-semibold">Priority</th>
                <th className="p-4 font-semibold">Task ID</th>
                <th className="p-4 font-semibold">Department</th>
                <th className="p-4 font-semibold">Location</th>
                <th className="p-4 font-semibold">Description</th>
                <th className="p-4 font-semibold">Duration</th>
                <th className="p-4 font-semibold text-right">Metrics</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50 text-sm">
              {filteredTasks.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-slate-500">
                    No tasks found matching criteria.
                  </td>
                </tr>
              ) : (
                filteredTasks.map(task => (
                  <tr key={task.task_id} className="hover:bg-slate-700/20 transition-colors group">
                    <td className="p-4 whitespace-nowrap">
                      {getPriorityBadge(task.priority_level, task.priority_score)}
                    </td>
                    <td className="p-4 font-mono text-slate-300">{task.task_id}</td>
                    <td className="p-4">
                      <span className={clsx("px-2 py-1 rounded text-xs font-semibold border", getDeptColor(task.department))}>
                        {task.department}
                      </span>
                    </td>
                    <td className="p-4">
                      <div className="font-medium text-slate-200">{task.corridor_id}</div>
                      <div className="text-xs text-slate-500">KM {task.location_km}</div>
                    </td>
                    <td className="p-4">
                      <div className="text-slate-300 line-clamp-1 group-hover:line-clamp-none">{task.description}</div>
                      {task.requires_isolation && (
                        <span className="inline-block mt-1 text-[10px] uppercase tracking-wider bg-red-500/10 text-red-400 px-1.5 py-0.5 rounded border border-red-500/20">
                          Isolation Required
                        </span>
                      )}
                    </td>
                    <td className="p-4 text-slate-300">
                      {task.duration_minutes}m
                    </td>
                    <td className="p-4 text-right">
                      <div className="flex flex-col items-end gap-1 text-xs">
                        {task.overdue_days > 0 ? (
                          <span className="text-orange-400 font-medium">{task.overdue_days}d overdue</span>
                        ) : (
                          <span className="text-slate-500">Due: {task.due_date}</span>
                        )}
                        <span className="text-slate-500" title="Train Impact Score">T-Imp: {task.train_impact.toFixed(2)}</span>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="p-3 bg-slate-900 border-t border-slate-700 text-xs text-slate-500 text-center">
          Showing {filteredTasks.length} of {tasks.length} tasks
        </div>
      </div>
    </div>
  );
}
