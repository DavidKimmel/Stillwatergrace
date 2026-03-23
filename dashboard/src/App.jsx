import { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import { startOfWeek } from 'date-fns';

import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import CalendarPage from './pages/CalendarPage';
import CreatorPage from './pages/CreatorPage';
import InsightsPage from './pages/InsightsPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  const [weekStart, setWeekStart] = useState(() =>
    startOfWeek(new Date(), { weekStartsOn: 1 }),
  );

  return (
    <div className="flex h-screen bg-brand-cream">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar weekStart={weekStart} onWeekChange={setWeekStart} />
        <main className="flex-1 overflow-auto p-6">
          <Routes>
            <Route path="/" element={<CalendarPage weekStart={weekStart} />} />
            <Route path="/creator" element={<CreatorPage />} />
            <Route path="/insights" element={<InsightsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
