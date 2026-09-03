import { useState } from 'react';
import { api } from '../services/api';
import { AlertTriangle, Play, RefreshCw, AlertOctagon, Zap, CheckCircle2 } from 'lucide-react';


export default function Simulation() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  
  // States for Train Delay
  const [trainId, setTrainId] = useState('EXP-101');
  const [delayMinutes, setDelayMinutes] = useState<number>(45);

  // States for New Defect
  const [department, setDepartment] = useState('ENGINEERING');
  const [corridorId, setCorridorId] = useState('C130');
  const [duration, setDuration] = useState<number>(120);
  const [locationKm, setLocationKm] = useState<number>(130.5);

  const runScenario = async (scenario: string) => {
    setLoading(true);
    try {
      await api.resetSimulation();
      
      let params = {};
      if (scenario === 'train_delay') {
        params = { train_id: trainId, delay_minutes: delayMinutes };
      } else {
        params = {
          department,
          corridor_id: corridorId,
          duration_minutes: duration,
          location_km: locationKm,
          defect_type: 'Emergency Defect',
          severity: 5,
          criticality: 5,
          safety_impact: 5
        };
      }

      const res = await api.injectEvent(scenario, params);
      
      // The API distinguishes 'new_defect' with event_type. 'train_delay' has res.event.train_id
      const isTrainDelay = scenario === 'train_delay';
      const isNewDefect = res.event_type === 'new_defect';

      // Immediately run reoptimize
      const optRes = await api.reoptimize();
      setResult({ 
        isTrainDelay,
        isNewDefect,
        event: res, 
        optimization: optRes 
      });
      
    } catch (e) {
      console.error(e);
      alert('Simulation failed.');
    } finally {
      setLoading(false);
    }
  };

  const reset = async () => {
    await api.resetSimulation();
    setResult(null);
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-5xl mx-auto pb-10">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white mb-1">Test Mode / Simulation</h1>
        <p className="text-slate-400">Inject unexpected real-world disruptions to test HYDRA's dynamic re-optimization capabilities.</p>
      </div>

      {!result ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 hover:border-orange-500/50 transition-colors group flex flex-col">
            <div className="w-12 h-12 bg-orange-500/20 rounded-lg flex items-center justify-center mb-4 border border-orange-500/30">
              <AlertTriangle className="w-6 h-6 text-orange-500" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">Scenario 1: Train Delay</h3>
            <p className="text-slate-400 text-sm mb-6 flex-1">
              Simulates a major train being delayed, causing its new path to overlap with a scheduled maintenance block.
            </p>
            
            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Train ID</label>
                <input type="text" value={trainId} onChange={e => setTrainId(e.target.value)} className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white focus:outline-none focus:border-orange-500 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Delay (minutes)</label>
                <input type="number" value={delayMinutes} onChange={e => setDelayMinutes(Number(e.target.value))} className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white focus:outline-none focus:border-orange-500 text-sm" />
              </div>
            </div>

            <button 
              onClick={() => runScenario('train_delay')}
              disabled={loading}
              className="w-full bg-slate-700 hover:bg-slate-600 text-white font-medium py-2.5 rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <Play className="w-4 h-4 text-orange-400" /> {loading ? 'Running...' : 'Run Scenario'}
            </button>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 hover:border-red-500/50 transition-colors group flex flex-col">
            <div className="w-12 h-12 bg-red-500/20 rounded-lg flex items-center justify-center mb-4 border border-red-500/30">
              <AlertOctagon className="w-6 h-6 text-red-500" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">Scenario 2: Emergency Defect</h3>
            <p className="text-slate-400 text-sm mb-6 flex-1">
              Simulates a critical weld failure or overhead line snap requiring an immediate emergency block.
            </p>

            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="col-span-2">
                <label className="block text-xs font-medium text-slate-400 mb-1">Department</label>
                <select value={department} onChange={e => setDepartment(e.target.value)} className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white focus:outline-none focus:border-red-500 text-sm">
                  <option value="ENGINEERING">Engineering</option>
                  <option value="SIGNALLING">Signalling</option>
                  <option value="TRACTION">Traction</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Corridor</label>
                <input type="text" value={corridorId} onChange={e => setCorridorId(e.target.value)} className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white focus:outline-none focus:border-red-500 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Location (KM)</label>
                <input type="number" step="0.1" value={locationKm} onChange={e => setLocationKm(Number(e.target.value))} className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white focus:outline-none focus:border-red-500 text-sm" />
              </div>
              <div className="col-span-2">
                <label className="block text-xs font-medium text-slate-400 mb-1">Duration (minutes)</label>
                <input type="number" value={duration} onChange={e => setDuration(Number(e.target.value))} className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white focus:outline-none focus:border-red-500 text-sm" />
              </div>
            </div>

            <button 
              onClick={() => runScenario('new_defect')}
              disabled={loading}
              className="w-full bg-slate-700 hover:bg-slate-600 text-white font-medium py-2.5 rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <Play className="w-4 h-4 text-red-400" /> {loading ? 'Running...' : 'Run Scenario'}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="flex justify-between items-center bg-slate-800 p-4 rounded-xl border border-slate-700">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-emerald-500/20 rounded-lg">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <h3 className="font-bold text-white">Re-optimization Complete</h3>
                <p className="text-sm text-slate-400">Solved in {result.optimization.optimization_time}s</p>
              </div>
            </div>
            <button onClick={reset} className="flex items-center gap-2 text-sm text-slate-300 hover:text-white px-4 py-2 bg-slate-700 rounded-lg transition-colors">
              <RefreshCw className="w-4 h-4" /> Reset Simulator
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Left: Event Details */}
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
              <h4 className="text-lg font-semibold text-white mb-4 border-b border-slate-700 pb-2">EVENT DETECTED</h4>
              {result.isTrainDelay ? (
                <div className="space-y-4 text-sm">
                  <div className="flex justify-between border-b border-slate-700 pb-2">
                    <span className="text-slate-400">Train:</span> 
                    <span className="font-mono text-white">{result.event.event.train_id}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-700 pb-2">
                    <span className="text-slate-400">Delay:</span> 
                    <span className="text-orange-400 font-bold">{result.event.event.delay_minutes} minutes</span>
                  </div>
                  
                  <div className="mt-4">
                    <span className="text-slate-400 block mb-2">Affected Blocks:</span>
                    {result.event.affected_blocks === 0 ? (
                      <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded border border-emerald-500/20 text-center font-semibold">
                        NO SCHEDULED BLOCKS AFFECTED
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {result.event.details.map((b: any) => (
                          <div key={b.block_id} className="p-2 bg-slate-900 border border-slate-700 rounded flex justify-between items-center">
                            <div>
                              <div className="font-mono text-white text-xs">{b.block_id}</div>
                              <div className="text-slate-500 text-[10px]">{b.corridor_id} ({b.start_time}-{b.end_time})</div>
                            </div>
                            <span className="text-red-400 text-xs">Conflicts: {b.conflicting_trains.join(', ')}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="space-y-4 text-sm">
                  <div className="flex justify-between border-b border-slate-700 pb-2">
                    <span className="text-slate-400">Defect Type:</span> 
                    <span className="text-red-400 font-bold uppercase">{result.event.new_task?.task_type}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-700 pb-2">
                    <span className="text-slate-400">Task ID:</span> 
                    <span className="font-mono text-white">{result.event.new_task?.task_id}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-700 pb-2">
                    <span className="text-slate-400">Location:</span> 
                    <span className="text-white">{result.event.new_task?.corridor_id} KM {result.event.new_task?.location_km}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-700 pb-2">
                    <span className="text-slate-400">Duration:</span> 
                    <span className="text-white">{result.event.new_task?.duration_minutes}m</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Priority:</span> 
                    <span className="bg-red-500/20 text-red-400 px-2 py-0.5 rounded font-bold text-xs">CRITICAL</span>
                  </div>
                </div>
              )}
            </div>

            {/* Right: Optimization Comparison */}
            <div className="bg-sky-900/20 border border-sky-500/30 rounded-xl p-6 relative overflow-hidden">
              <Zap className="w-32 h-32 absolute -right-4 -bottom-4 text-sky-500/10 pointer-events-none" />
              <h4 className="text-lg font-semibold text-sky-400 mb-4 border-b border-sky-500/20 pb-2 relative z-10">HYDRA Response</h4>
              
              <div className="relative z-10">
                <div className="grid grid-cols-3 gap-2 text-xs font-bold text-slate-500 mb-2 px-2">
                  <div>METRIC</div>
                  <div className="text-right">BEFORE</div>
                  <div className="text-right">AFTER</div>
                </div>
                
                <div className="space-y-2">
                  <div className="grid grid-cols-3 gap-2 p-2 bg-slate-900/50 rounded items-center">
                    <div className="text-slate-300 text-sm">Blocks</div>
                    <div className="text-right font-mono text-slate-400">{result.optimization.before.total_blocks}</div>
                    <div className="text-right font-mono text-white">{result.optimization.after.total_blocks}</div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 p-2 bg-slate-900/50 rounded items-center">
                    <div className="text-slate-300 text-sm">Tasks Done</div>
                    <div className="text-right font-mono text-slate-400">{result.optimization.before.tasks_completed}</div>
                    <div className="text-right font-mono text-white">{result.optimization.after.tasks_completed}</div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 p-2 bg-slate-900/50 rounded items-center">
                    <div className="text-slate-300 text-sm">Tasks Deferred</div>
                    <div className="text-right font-mono text-slate-400">{result.optimization.before.tasks_deferred}</div>
                    <div className="text-right font-mono text-orange-400">{result.optimization.after.tasks_deferred}</div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 p-2 bg-slate-900/50 rounded items-center">
                    <div className="text-slate-300 text-sm">Block Hours</div>
                    <div className="text-right font-mono text-slate-400">{result.optimization.before.total_block_hours}</div>
                    <div className="text-right font-mono text-white">{result.optimization.after.total_block_hours}</div>
                  </div>
                </div>

                <div className="mt-6 p-3 bg-sky-500/10 border border-sky-500/20 rounded text-sm text-sky-200">
                  Rescheduled <strong>{result.optimization.changes.tasks_rescheduled}</strong> tasks automatically to resolve conflicts. 
                  View the new schedule in the Weekly Planner.
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
