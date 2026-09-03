import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { Train, ListTodo, CalendarDays, Activity, Settings2 } from 'lucide-react';
import { clsx } from 'clsx';
import Dashboard from './pages/Dashboard';
import Tasks from './pages/Tasks';
import Planner from './pages/Planner';
import Simulation from './pages/Simulation';

function App() {
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Dashboard', icon: Activity },
    { path: '/tasks', label: 'Priority Queue', icon: ListTodo },
    { path: '/planner', label: 'Weekly Planner', icon: CalendarDays },
    { path: '/simulation', label: 'Test Mode', icon: Settings2 },
  ];

  return (
    <div className="flex h-screen bg-slate-900 text-slate-100 overflow-hidden font-sans">
      {/* Sidebar */}
      <div className="w-64 bg-slate-800 border-r border-slate-700 flex flex-col">
        <div className="p-5 flex items-center gap-3 border-b border-slate-700">
          <div className="bg-sky-500 p-2 rounded-lg">
            <Train className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-xl tracking-tight text-white">HYDRA</h1>
            <p className="text-xs text-sky-400 font-medium">Block Planning Engine</p>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4 px-2">Menu</div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={clsx(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                  isActive 
                    ? "bg-sky-500/10 text-sky-400" 
                    : "text-slate-300 hover:bg-slate-700 hover:text-white"
                )}
              >
                <Icon className={clsx("w-5 h-5", isActive ? "text-sky-400" : "text-slate-400")} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        
        <div className="p-4 border-t border-slate-700">
          <div className="bg-slate-900 rounded border border-slate-700 p-3 text-xs">
            <div className="flex items-center gap-2 mb-1">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
              <span className="font-medium text-slate-300">System Online</span>
            </div>
            <p className="text-slate-500">Decision Support Prototype</p>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        <div className="absolute top-0 right-0 p-4 z-10 pointer-events-none">
           <div className="bg-amber-500/10 border border-amber-500/20 text-amber-500 px-3 py-1 rounded-full text-xs font-medium flex items-center gap-2 shadow-sm backdrop-blur-sm">
             <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>
             Human Approval Required
           </div>
        </div>
        <div className="flex-1 overflow-y-auto p-6 md:p-8 bg-slate-900">
          <div className="max-w-7xl mx-auto">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/tasks" element={<Tasks />} />
              <Route path="/planner" element={<Planner />} />
              <Route path="/simulation" element={<Simulation />} />
            </Routes>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
