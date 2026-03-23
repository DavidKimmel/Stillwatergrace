import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  CalendarDays,
  PenTool,
  BarChart3,
  Settings,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';

const NAV_ITEMS = [
  { to: '/', icon: CalendarDays, label: 'Calendar' },
  { to: '/creator', icon: PenTool, label: 'Creator' },
  { to: '/insights', icon: BarChart3, label: 'Insights' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

const R2_URL = 'https://dash.cloudflare.com/7cdee1457e807faf5dc3a887bdf85a62/r2/default/buckets/stillwatergrace-images?prefix=images%2F';

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className="bg-brand-green flex flex-col shrink-0 transition-all duration-200"
      style={{ width: collapsed ? 64 : 220 }}
    >
      {/* Logo */}
      <div className="flex items-center h-16 border-b border-white/10 px-4">
        <span className="font-heading text-brand-gold text-xl font-bold tracking-wide">
          {collapsed ? 'S' : 'SWG'}
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 flex flex-col gap-1">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 py-3 text-sm transition-colors ${
                collapsed ? 'justify-center px-0' : 'px-5'
              } ${
                isActive
                  ? 'text-brand-gold border-l-[3px] border-brand-gold bg-white/10'
                  : 'text-brand-cream/70 hover:text-brand-cream hover:bg-white/5 border-l-[3px] border-transparent'
              }`
            }
          >
            <Icon size={20} />
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}
        {/* R2 Storage link */}
        <a
          href={R2_URL}
          target="_blank"
          rel="noopener noreferrer"
          className={`flex items-center gap-3 py-3 text-sm transition-colors text-brand-cream/70 hover:text-brand-cream hover:bg-white/5 border-l-[3px] border-transparent ${
            collapsed ? 'justify-center px-0' : 'px-5'
          }`}
        >
          <ExternalLink size={20} />
          {!collapsed && <span>R2 Storage</span>}
        </a>
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed((prev) => !prev)}
        className="flex items-center justify-center h-12 border-t border-white/10 text-brand-cream/50 hover:text-brand-cream transition-colors"
      >
        {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
      </button>
    </aside>
  );
}
