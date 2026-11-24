import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Valuation } from "../api";

function formatCompact(value: number): string {
  if (value >= 1_000_000) return `€${(value / 1_000_000).toFixed(0)}m`;
  if (value >= 1_000) return `€${(value / 1_000).toFixed(0)}k`;
  return `€${value}`;
}

const CREST_SIZE = 22;

function TransferDot(props: {
  cx?: number;
  cy?: number;
  payload?: { crest?: string | null; isTransfer?: boolean; club?: string | null };
}) {
  const { cx, cy, payload } = props;
  if (cx == null || cy == null || !payload) return null;
  if (!payload.isTransfer) {
    return <circle cx={cx} cy={cy} r={2.5} fill="var(--accent)" stroke="var(--surface)" strokeWidth={1} />;
  }
  if (!payload.crest) {
    return <circle cx={cx} cy={cy} r={4} fill="var(--accent-text)" stroke="var(--surface)" strokeWidth={1.5} />;
  }
  const clipId = `crest-clip-${Math.round(cx)}-${Math.round(cy)}`;
  const half = CREST_SIZE / 2;
  return (
    <g>
      <circle cx={cx} cy={cy} r={half + 2} fill="var(--surface)" stroke="var(--accent)" strokeWidth={1.5} />
      <defs>
        <clipPath id={clipId}>
          <circle cx={cx} cy={cy} r={half} />
        </clipPath>
      </defs>
      <image
        href={payload.crest}
        x={cx - half}
        y={cy - half}
        width={CREST_SIZE}
        height={CREST_SIZE}
        clipPath={`url(#${clipId})`}
        preserveAspectRatio="xMidYMid slice"
      >
        <title>{payload.club ?? ""}</title>
      </image>
    </g>
  );
}

export default function MarketValueChart({ valuations }: { valuations: Valuation[] }) {
  if (valuations.length < 2) return null;

  const data = valuations.map((v, i) => ({
    date: new Date(v.date).toLocaleDateString("nl-BE", { month: "short", year: "numeric" }),
    value: v.market_value_in_eur,
    club: v.club_name,
    crest: v.club_crest_url,
    isTransfer: i === 0 || v.club_name !== valuations[i - 1].club_name,
  }));

  return (
    <div className="card">
      <h3 style={{ marginBottom: 2 }}>Marktwaarde door de tijd</h3>
      <p className="muted" style={{ fontSize: "0.76rem", marginTop: 0, marginBottom: 8 }}>
        Clublogo = moment van transfer
      </p>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={data} margin={{ top: 14, right: 16, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="mvFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.4} />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            tick={{ fill: "var(--text-faint)", fontSize: 10.5 }}
            interval="preserveStartEnd"
            axisLine={{ stroke: "var(--border)" }}
            tickLine={false}
          />
          <YAxis
            tickFormatter={formatCompact}
            tick={{ fill: "var(--text-faint)", fontSize: 10.5 }}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <Tooltip
            formatter={(v: number) => formatCompact(v)}
            labelFormatter={(label, items) => {
              const club = (items?.[0]?.payload as { club?: string })?.club;
              return club ? `${label} · ${club}` : label;
            }}
            contentStyle={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: "0.8rem",
            }}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke="var(--accent)"
            fill="url(#mvFill)"
            strokeWidth={2}
            dot={<TransferDot />}
            activeDot={{ r: 5 }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
