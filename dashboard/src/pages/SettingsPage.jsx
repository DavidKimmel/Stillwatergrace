export default function SettingsPage() {
  const trackedAccounts = [
    'youversion',
    'thedailygraceco',
    'bibleverse',
    'proverbs31ministries',
    'shereadstruth',
  ];

  const systemServices = [
    { name: 'API', status: 'online' },
    { name: 'Database', status: 'online' },
    { name: 'Redis', status: 'online' },
    { name: 'Celery Worker', status: 'online' },
    { name: 'Celery Beat', status: 'online' },
  ];

  const platforms = [
    { name: 'Instagram', handle: '@stillwatergrace', status: 'connected' },
    { name: 'Facebook', handle: 'Still Water Grace', status: 'connected' },
    { name: 'TikTok', handle: '', status: 'sandbox' },
  ];

  return (
    <div className="space-y-6">
      <h1 className="font-heading text-2xl text-brand-green">Settings</h1>

      {/* Content Generation */}
      <section className="bg-white rounded-xl shadow-warm p-6">
        <h2 className="font-heading text-lg text-brand-green mb-4">
          Content Generation
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <SettingItem label="Default Generation Days">
            <select
              className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-gray-50 cursor-default"
              defaultValue={3}
              disabled
            >
              {[1, 2, 3, 4, 5, 6, 7].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </SettingItem>
          <SettingItem label="Generation Time">
            <span className="text-sm text-gray-700">5:15 AM EST</span>
          </SettingItem>
          <SettingItem label="Image Generation Time">
            <span className="text-sm text-gray-700">5:45 AM EST</span>
          </SettingItem>
        </div>
      </section>

      {/* Posting Schedule */}
      <section className="bg-white rounded-xl shadow-warm p-6">
        <h2 className="font-heading text-lg text-brand-green mb-4">
          Posting Schedule
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <SettingItem label="Morning Slot">
            <span className="text-sm text-gray-700">6:30 AM EST</span>
          </SettingItem>
          <SettingItem label="Noon Slot">
            <span className="text-sm text-gray-700">12:00 PM EST</span>
          </SettingItem>
          <SettingItem label="Auto-Approve">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
              OFF
            </span>
          </SettingItem>
        </div>
      </section>

      {/* Competitor Scraper */}
      <section className="bg-white rounded-xl shadow-warm p-6">
        <h2 className="font-heading text-lg text-brand-green mb-4">
          Competitor Scraper
        </h2>
        <div className="space-y-3">
          <SettingItem label="Schedule">
            <span className="text-sm text-gray-700">
              Monday, Wednesday, Friday at 5:00 AM EST
            </span>
          </SettingItem>
          <SettingItem label="Tracked Accounts">
            <div className="flex flex-wrap gap-2 mt-1">
              {trackedAccounts.map((account) => (
                <span
                  key={account}
                  className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-brand-cream text-brand-green border border-brand-gold/30"
                >
                  @{account}
                </span>
              ))}
            </div>
          </SettingItem>
        </div>
      </section>

      {/* System Status */}
      <section className="bg-white rounded-xl shadow-warm p-6">
        <h2 className="font-heading text-lg text-brand-green mb-4">
          System Status
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          {systemServices.map((service) => (
            <div
              key={service.name}
              className="flex items-center gap-2 text-sm text-gray-700"
            >
              <span className="h-2.5 w-2.5 rounded-full bg-green-500 flex-shrink-0" />
              {service.name}
            </div>
          ))}
        </div>
      </section>

      {/* Connected Platforms */}
      <section className="bg-white rounded-xl shadow-warm p-6">
        <h2 className="font-heading text-lg text-brand-green mb-4">
          Connected Platforms
        </h2>
        <div className="space-y-3">
          {platforms.map((platform) => (
            <div
              key={platform.name}
              className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0"
            >
              <div>
                <span className="text-sm font-medium text-gray-800">
                  {platform.name}
                </span>
                {platform.handle && (
                  <span className="text-sm text-gray-500 ml-2">
                    {platform.handle}
                  </span>
                )}
              </div>
              {platform.status === 'connected' ? (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                  Connected
                </span>
              ) : (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
                  Sandbox
                </span>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function SettingItem({ label, children }) {
  return (
    <div>
      <dt className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
        {label}
      </dt>
      <dd>{children}</dd>
    </div>
  );
}
