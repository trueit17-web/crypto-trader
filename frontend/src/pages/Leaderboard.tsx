import React, { useState } from 'react';

interface SourceStats {
  rank: number;
  source: string;
  trades: number;
  win_rate: number | null;
  win_rate_7d: number | null;
  win_rate_30d: number | null;
  net_pnl: number;
  avg_pnl: number | null;
  profit_factor: number | null;
  sharpe: number | null;
  max_drawdown: number;
  status: 'active' | 'reduced' | 'shadow' | 'suspended';
}

const MOCK_DATA: SourceStats[] = [
  { rank:1, source:'@crypto_alpha',  trades:124, win_rate:67.7, win_rate_7d:71, win_rate_30d:68, net_pnl:342.8, avg_pnl:2.76, profit_factor:2.4, sharpe:1.87, max_drawdown:4.2, status:'active' },
  { rank:2, source:'@scalp_pro',     trades:89,  win_rate:61.8, win_rate_7d:65, win_rate_30d:60, net_pnl:187.3, avg_pnl:2.10, profit_factor:1.9, sharpe:1.42, max_drawdown:6.8, status:'active' },
  { rank:3, source:'TradingView/BTC',trades:43,  win_rate:58.1, win_rate_7d:55, win_rate_30d:58, net_pnl:98.4,  avg_pnl:2.29, profit_factor:1.7, sharpe:1.21, max_drawdown:5.1, status:'active' },
  { rank:4, source:'@whale_signals', trades:67,  win_rate:47.8, win_rate_7d:40, win_rate_30d:48, net_pnl:12.6,  avg_pnl:0.19, profit_factor:1.1, sharpe:0.31, max_drawdown:11.3, status:'reduced' },
  { rank:5, source:'@pumpit_x',      trades:31,  win_rate:32.3, win_rate_7d:28, win_rate_30d:33, net_pnl:-67.2, avg_pnl:-2.17,profit_factor:0.5, sharpe:-0.8, max_drawdown:18.7, status:'suspended' },
];

const STATUS_COLORS: Record<string, string> = {
  active:    'bg-green-500/20 text-green-400',
  reduced:   'bg-yellow-500/20 text-yellow-400',
  shadow:    'bg-gray-500/20 text-gray-400',
  suspended: 'bg-red-500/20 text-red-400',
};
const STATUS_LABELS: Record<string, string> = {
  active:'Активен', reduced:'Снижен', shadow:'Тень', suspended:'Блок',
};

export default function Leaderboard() {
  const [sortBy, setSortBy] = useState<keyof SourceStats>('rank');
  const [filter, setFilter] = useState('');

  const sorted = [...MOCK_DATA]
    .filter(s => s.source.toLowerCase().includes(filter.toLowerCase()))
    .sort((a, b) => {
      const av = a[sortBy] as number ?? 0;
      const bv = b[sortBy] as number ?? 0;
      return sortBy === 'rank' ? av - bv : bv - av;
    });

  const Th = ({ k, label }: { k: keyof SourceStats; label: string }) => (
    <th
      className={`px-3 py-2 text-left text-xs font-medium cursor-pointer select-none hover:text-white transition-colors ${
        sortBy === k ? 'text-yellow-400' : 'text-gray-400'
      }`}
      onClick={() => setSortBy(k)}
    >
      {label} {sortBy === k ? '↓' : ''}
    </th>
  );

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Рейтинг источников</h1>
          <p className="text-gray-400 text-sm mt-1">
            Производительность каждого сигнального источника за последние 30 дней
          </p>
        </div>
        <input
          type="text" placeholder="Поиск источника..."
          value={filter} onChange={e => setFilter(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-yellow-500"
        />
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label:'Всего источников', value: MOCK_DATA.length },
          { label:'Активных', value: MOCK_DATA.filter(s=>s.status==='active').length, color:'text-green-400' },
          { label:'Заблокированных', value: MOCK_DATA.filter(s=>s.status==='suspended').length, color:'text-red-400' },
          { label:'Лучший Win Rate', value: `${Math.max(...MOCK_DATA.map(s=>s.win_rate||0))}%`, color:'text-yellow-400' },
        ].map(c => (
          <div key={c.label} className="bg-gray-800 rounded-xl p-4 border border-gray-700">
            <div className="text-gray-400 text-xs mb-1">{c.label}</div>
            <div className={`text-2xl font-bold ${c.color || 'text-white'}`}>{c.value}</div>
          </div>
        ))}
      </div>

      {/* Table */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-900/50">
            <tr>
              <Th k="rank" label="#" />
              <Th k="source" label="Источник" />
              <Th k="trades" label="Сделок" />
              <Th k="win_rate" label="Win Rate" />
              <Th k="win_rate_7d" label="7д" />
              <Th k="win_rate_30d" label="30д" />
              <Th k="net_pnl" label="Net P&L" />
              <Th k="avg_pnl" label="Avg P&L" />
              <Th k="profit_factor" label="PF" />
              <Th k="sharpe" label="Sharpe" />
              <Th k="max_drawdown" label="Max DD" />
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-400">Статус</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {sorted.map(s => (
              <tr key={s.source} className="hover:bg-gray-700/30 transition-colors">
                <td className="px-3 py-3 text-sm font-bold text-gray-400">#{s.rank}</td>
                <td className="px-3 py-3">
                  <div className="text-sm font-medium">{s.source}</div>
                </td>
                <td className="px-3 py-3 text-sm text-center">{s.trades}</td>
                <td className="px-3 py-3 text-sm text-center font-semibold">
                  <span className={s.win_rate && s.win_rate >= 55 ? 'text-green-400' : 'text-red-400'}>
                    {s.win_rate?.toFixed(1)}%
                  </span>
                </td>
                <td className="px-3 py-3 text-sm text-center text-gray-400">{s.win_rate_7d}%</td>
                <td className="px-3 py-3 text-sm text-center text-gray-400">{s.win_rate_30d}%</td>
                <td className={`px-3 py-3 text-sm font-semibold ${
                  s.net_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>{s.net_pnl >= 0 ? '+' : ''}{s.net_pnl.toFixed(1)}%</td>
                <td className={`px-3 py-3 text-sm ${
                  (s.avg_pnl||0) >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>{s.avg_pnl?.toFixed(2)}%</td>
                <td className="px-3 py-3 text-sm text-center">{s.profit_factor?.toFixed(2)}</td>
                <td className="px-3 py-3 text-sm text-center">{s.sharpe?.toFixed(2)}</td>
                <td className="px-3 py-3 text-sm text-center text-red-400">{s.max_drawdown.toFixed(1)}%</td>
                <td className="px-3 py-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${STATUS_COLORS[s.status]}`}>
                    {STATUS_LABELS[s.status]}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
