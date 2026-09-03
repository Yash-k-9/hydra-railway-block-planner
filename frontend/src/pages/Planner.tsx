import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { Calendar, Clock, MapPin, Zap, CheckCircle2, XCircle, Settings, List, Map as MapIcon, X } from 'lucide-react';
import { clsx } from 'clsx';
import HyderabadMap from '../components/HyderabadMap';

export default function Planner() {
  const [loading, setLoading] = useState(true);
  const [weeklyPlan, setWeeklyPlan] = useState<any>(null);
  const [selectedBlock, setSelectedBlock] = useState<any>(null);
  const [blockDetail, setBlockDetail] = useState<any>(null);
  const [approving, setApproving] = useState(false);
  const [viewMode, setViewMode] = useState<'schedule' | 'map'>('schedule');

  useEffect(() => {
    const fetchPlan = async () => {
      try {
        const res = await api.getWeeklyPlan();
        setWeeklyPlan(res.weekly_plan);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchPlan();
  }, []);

  const handleBlockClick = async (block: any) => {
    setSelectedBlock(block);
    setBlockDetail(null);
    try {
      const detail = await api.getBlockDetail(block.block_id);
      setBlockDetail(detail);
    } catch (e) {
      console.error(e);
    }
  };

  const handleMapBlockSelect = (blockId: string | null) => {
    if (!blockId) {
      setSelectedBlock(null);
      setBlockDetail(null);
      return;
    }
    const allBlocks = weeklyPlan ? Object.values(weeklyPlan).flat() : [];
    const block = allBlocks.find((b: any) => b.block_id === blockId);
    if (block) {
      handleBlockClick(block);
    }
  };

  const handleApproval = async (action: 'approve' | 'reject') => {
    if (!selectedBlock) return;
    setApproving(true);
    try {
      await api.approveBlock({ block_id: selectedBlock.block_id, action });
      // Update local state for immediate feedback
      setSelectedBlock({ ...selectedBlock, status: action === 'approve' ? 'approved' : 'rejected' });
      
      // Update in weekly plan
      const newPlan = { ...weeklyPlan };
      for (const date in newPlan) {
        const idx = newPlan[date].findIndex((b: any) => b.block_id === selectedBlock.block_id);
        if (idx !== -1) {
          newPlan[date][idx].status = action === 'approve' ? 'approved' : 'rejected';
        }
      }
      setWeeklyPlan(newPlan);
    } catch (e) {
      console.error(e);
    } finally {
      setApproving(false);
    }
  };

  if (loading) {
    return <div className="animate-pulse h-full bg-slate-800 rounded-xl p-8">Loading schedule...</div>;
  }

  if (!weeklyPlan || Object.keys(weeklyPlan).length === 0) {
    return (
      <div className="text-center mt-20">
        <h2 className="text-xl font-medium text-slate-300">No optimized plan available.</h2>
        <p className="text-slate-500 mt-2">Run the optimization pipeline from the dashboard first.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col lg:flex-row h-full gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Schedule View */}
      <div className="flex-1 flex flex-col space-y-6">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white mb-1">Weekly Planner</h1>
            <p className="text-slate-400">Optimized maintenance block schedule avoiding train conflicts.</p>
          </div>
          <div className="flex bg-slate-800 rounded-lg p-1 border border-slate-700">
            <button 
              onClick={() => setViewMode('schedule')}
              className={clsx("px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2", viewMode === 'schedule' ? "bg-sky-500 text-white shadow-sm" : "text-slate-400 hover:text-slate-200 hover:bg-slate-700/50")}
            >
              <List className="w-4 h-4" /> Schedule
            </button>
            <button 
              onClick={() => setViewMode('map')}
              className={clsx("px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2", viewMode === 'map' ? "bg-sky-500 text-white shadow-sm" : "text-slate-400 hover:text-slate-200 hover:bg-slate-700/50")}
            >
              <MapIcon className="w-4 h-4" /> Map
            </button>
          </div>
        </div>

        {viewMode === 'schedule' ? (
          <div className="flex-1 overflow-y-auto space-y-8 pr-2 custom-scrollbar">
          {Object.entries(weeklyPlan).map(([date, blocks]: [string, any]) => (
            <div key={date} className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden shadow-sm">
              <div className="bg-slate-900/80 p-3 px-5 border-b border-slate-700 flex items-center gap-3 sticky top-0 z-10 backdrop-blur-md">
                <Calendar className="w-5 h-5 text-sky-400" />
                <h2 className="font-semibold text-slate-200">
                  {new Date(date).toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
                </h2>
                <div className="ml-auto flex gap-2">
                  <span className="text-xs bg-slate-800 border border-slate-700 px-2 py-1 rounded text-slate-400 font-medium">
                    {blocks.length} Blocks
                  </span>
                </div>
              </div>
              
              <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                {blocks.map((block: any) => {
                  const isSelected = selectedBlock?.block_id === block.block_id;
                  const statusColor = 
                    block.status === 'approved' ? 'border-emerald-500/50 bg-emerald-500/5' :
                    block.status === 'rejected' ? 'border-red-500/50 bg-red-500/5' :
                    isSelected ? 'border-sky-500 bg-sky-500/10 shadow-[0_0_15px_rgba(56,189,248,0.2)]' : 'border-slate-700 bg-slate-900/50 hover:border-slate-500 hover:bg-slate-700/30';

                  return (
                    <div 
                      key={block.block_id}
                      onClick={() => handleBlockClick(block)}
                      className={clsx(
                        "p-4 rounded-lg border transition-all cursor-pointer relative",
                        statusColor
                      )}
                    >
                      {block.is_multi_department && (
                        <div className="absolute -top-2 -right-2 bg-gradient-to-r from-sky-500 to-indigo-500 text-white text-[10px] font-bold px-2 py-0.5 rounded shadow-sm border border-white/20">
                          BUNDLED
                        </div>
                      )}
                      
                      <div className="flex justify-between items-start mb-3">
                        <div className="font-mono text-sm font-semibold text-slate-300">{block.block_id}</div>
                        <div className="flex items-center gap-1.5 text-slate-300 bg-slate-800 px-2 py-1 rounded text-xs border border-slate-700">
                          <Clock className="w-3.5 h-3.5 text-slate-400" />
                          <span className="font-medium">{block.start_time} - {block.end_time}</span>
                          <span className="text-slate-500">({block.duration_minutes}m)</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 mb-4 text-sm">
                        <MapPin className="w-4 h-4 text-slate-400" />
                        <span className="font-medium text-slate-200">{block.corridor_id}</span>
                      </div>

                      <div className="space-y-1.5">
                        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Departments</div>
                        <div className="flex flex-wrap gap-1.5">
                          {block.departments.map((dept: string) => (
                            <span key={dept} className={clsx(
                              "px-2 py-0.5 rounded text-xs font-medium border",
                              dept === 'ENGINEERING' ? 'bg-sky-500/10 text-sky-400 border-sky-500/20' :
                              dept === 'SIGNALLING' ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' :
                              'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
                            )}>
                              {dept}
                            </span>
                          ))}
                        </div>
                      </div>
                      
                      {/* Utilization Bar */}
                      <div className="mt-4 pt-3 border-t border-slate-700/50">
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-slate-400">Capacity Used</span>
                          <span className={clsx("font-medium", block.utilization > 90 ? 'text-orange-400' : 'text-slate-300')}>{block.utilization}%</span>
                        </div>
                        <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                          <div 
                            className={clsx("h-full rounded-full transition-all duration-1000", 
                              block.utilization > 90 ? 'bg-orange-500' : 'bg-sky-500'
                            )}
                            style={{ width: `${Math.min(100, block.utilization)}%` }}
                          ></div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
        ) : (
          <div className="flex-1 relative z-0 h-full rounded-xl overflow-hidden border border-slate-700 shadow-sm">
            <HyderabadMap 
              blocks={weeklyPlan ? Object.values(weeklyPlan).flat() : []}
              selectedBlockId={selectedBlock?.block_id}
              blockDetail={blockDetail}
              onBlockSelect={handleMapBlockSelect}
            />
          </div>
        )}
      </div>

      {/* Inspector Panel */}
      <div className="w-full lg:w-96 bg-slate-800 border border-slate-700 rounded-xl shadow-xl flex flex-col h-[calc(100vh-8rem)] shrink-0 lg:sticky top-0">
        <div className="p-4 border-b border-slate-700 bg-slate-900/50 rounded-t-xl flex justify-between items-center">
          <h2 className="font-semibold text-lg flex items-center gap-2">
            <Zap className="w-5 h-5 text-sky-400" />
            Block Inspector
          </h2>
          {selectedBlock && (
            <button 
              onClick={() => handleMapBlockSelect(null)}
              className="text-slate-400 hover:text-white transition-colors p-1 bg-slate-800 rounded-md border border-slate-700 hover:bg-slate-700"
              title="Deselect Block"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {!selectedBlock ? (
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-slate-500">
            <Calendar className="w-12 h-12 mb-3 opacity-20" />
            <p>Select a maintenance block from the schedule to view details and approve.</p>
          </div>
        ) : !blockDetail ? (
          <div className="p-6 text-center text-slate-500 animate-pulse">Loading block details...</div>
        ) : (
          <div className="flex-1 overflow-y-auto p-5 space-y-6">
            
            {/* Header info */}
            <div>
              <div className="flex justify-between items-start mb-2">
                <h3 className="text-xl font-bold font-mono text-white">{selectedBlock.block_id}</h3>
                {selectedBlock.status === 'approved' && <span className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider flex items-center gap-1"><CheckCircle2 className="w-3 h-3"/> Approved</span>}
                {selectedBlock.status === 'rejected' && <span className="bg-red-500/20 text-red-400 border border-red-500/30 px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider flex items-center gap-1"><XCircle className="w-3 h-3"/> Rejected</span>}
                {selectedBlock.status === 'generated' && <span className="bg-slate-700 text-slate-300 border border-slate-600 px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider">Pending Review</span>}
              </div>
              <div className="grid grid-cols-2 gap-3 mt-4">
                <div className="bg-slate-900 p-3 rounded-lg border border-slate-700">
                  <div className="text-xs text-slate-500 mb-1 font-medium uppercase">Date</div>
                  <div className="text-sm font-semibold text-slate-200">{selectedBlock.date}</div>
                </div>
                <div className="bg-slate-900 p-3 rounded-lg border border-slate-700">
                  <div className="text-xs text-slate-500 mb-1 font-medium uppercase">Time Window</div>
                  <div className="text-sm font-semibold text-slate-200">{selectedBlock.start_time} - {selectedBlock.end_time}</div>
                </div>
                <div className="bg-slate-900 p-3 rounded-lg border border-slate-700">
                  <div className="text-xs text-slate-500 mb-1 font-medium uppercase">Corridor</div>
                  <div className="text-sm font-semibold text-slate-200">{selectedBlock.corridor_id}</div>
                </div>
                <div className="bg-slate-900 p-3 rounded-lg border border-slate-700">
                  <div className="text-xs text-slate-500 mb-1 font-medium uppercase">Tasks</div>
                  <div className="text-sm font-semibold text-slate-200">{selectedBlock.tasks.length} included</div>
                </div>
              </div>
            </div>

            {/* AI Rationale */}
            <div className="bg-sky-900/20 border border-sky-500/30 rounded-lg p-4">
              <h4 className="text-sm font-semibold text-sky-400 mb-3 flex items-center gap-2">
                <Settings className="w-4 h-4" /> Optimization Rationale
              </h4>
              <ul className="space-y-2">
                {blockDetail.explanation.map((reason: string, i: number) => (
                  <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                    <span className="text-sky-500 mt-0.5">•</span>
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Tasks List */}
            <div>
              <h4 className="text-sm font-semibold text-slate-300 mb-3 border-b border-slate-700 pb-2">Included Tasks</h4>
              <div className="space-y-2">
                {blockDetail.block.tasks.map((task: any) => (
                  <div key={task.task_id} className="bg-slate-900 p-3 rounded-lg border border-slate-700 text-sm">
                    <div className="flex justify-between items-start mb-1">
                      <span className="font-mono font-medium text-slate-300">{task.task_id}</span>
                      <span className={clsx(
                        "text-[10px] font-bold px-1.5 py-0.5 rounded",
                        task.priority_level === 'CRITICAL' ? 'bg-red-500/20 text-red-400' :
                        task.priority_level === 'HIGH' ? 'bg-orange-500/20 text-orange-400' :
                        'bg-slate-700 text-slate-400'
                      )}>{task.priority_level}</span>
                    </div>
                    <div className="text-slate-400 text-xs flex justify-between mt-2">
                      <span>{task.department}</span>
                      <span>{task.duration_minutes}m</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        )}

        {/* Action Buttons */}
        {selectedBlock && (
          <div className="p-4 border-t border-slate-700 bg-slate-900/50 rounded-b-xl grid grid-cols-2 gap-3">
            <button
              onClick={() => handleApproval('reject')}
              disabled={approving || selectedBlock.status === 'rejected'}
              className="py-2.5 rounded-lg font-medium text-sm transition-all border border-red-500/50 text-red-400 hover:bg-red-500/10 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <XCircle className="w-4 h-4"/> Reject
            </button>
            <button
              onClick={() => handleApproval('approve')}
              disabled={approving || selectedBlock.status === 'approved'}
              className="py-2.5 rounded-lg font-medium text-sm transition-all bg-emerald-600 hover:bg-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.3)] disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <CheckCircle2 className="w-4 h-4"/> Approve
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
