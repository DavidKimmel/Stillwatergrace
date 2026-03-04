import { Routes, Route, NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  ListChecks,
  Calendar,
  BarChart3,
  Users,
  DollarSign,
  Settings,
} from 'lucide-react';

import DashboardPage from './pages/DashboardPage';
import QueuePage from './pages/QueuePage';
import CalendarPage from './pages/CalendarPage';
import AnalyticsPage from './pages/AnalyticsPage';
import CompetitorsPage from './pages/CompetitorsPage';
import MonetizationPage from './pages/MonetizationPage';

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/queue', icon: ListChecks, label: 'Content Queue' },
  { to: '/calendar', icon: Calendar, label: 'Calendar' },
  { to: '/analytics', icon: BarChart3, label: 'Analytics' },
  { to: '/competitors', icon: Users, label: 'Competitors' },
  { to: '/monetization', icon: DollarSign, label: 'Monetization' },
];

export default function App() {
  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-64 bg-brand-green text-white flex flex-col shrink-0">
        <div className="p-6 border-b border-white/10">
          <h1 className="font-heading text-xl font-bold text-brand-gold">
            StillWaterGrace
          </h1>
          <p className="text-xs text-white/60 mt-1">Content Dashboard</p>
        </div>

        <nav className="flex-1 py-4">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-6 py-3 text-sm transition-colors ${
                  isActive
                    ? 'bg-white/10 text-brand-gold border-r-2 border-brand-gold'
                    : 'text-white/70 hover:text-white hover:bg-white/5'
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-white/10 text-xs text-white/40">
          v0.1.0
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="p-8 max-w-7xl mx-auto">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/queue" element={<QueuePage />} />
            <Route path="/calendar" element={<CalendarPage />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="/competitors" element={<CompetitorsPage />} />
            <Route path="/monetization" element={<MonetizationPage />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}
