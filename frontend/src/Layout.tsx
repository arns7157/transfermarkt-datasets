import { Scale, Search, Shield, Siren, Sprout, Target, Trophy } from "lucide-react";
import type { ComponentType } from "react";
import { NavLink, Outlet } from "react-router-dom";

const groups: { label: string; links: { to: string; label: string; icon: ComponentType<{ size?: number }>; end?: boolean }[] }[] = [
  {
    label: "Spelers",
    links: [
      { to: "/", label: "Spelers zoeken", icon: Search, end: true },
      { to: "/potentie", label: "Potentie", icon: Sprout },
      { to: "/vergelijken", label: "Vergelijken", icon: Scale },
      { to: "/signalen", label: "Signalen", icon: Siren },
    ],
  },
  {
    label: "Data",
    links: [
      { to: "/clubs", label: "Clubs", icon: Shield },
      { to: "/competities", label: "Competities", icon: Trophy },
      { to: "/fotmob", label: "FotMob", icon: Target },
    ],
  },
];

export default function Layout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="dot" />
          Transfermarkt Datasets
        </div>
        <nav className="sidebar-nav">
          {groups.map((group) => (
            <div key={group.label}>
              <div className="sidebar-section-label">{group.label}</div>
              {group.links.map((l) => {
                const Icon = l.icon;
                return (
                  <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => (isActive ? "active" : "")}>
                    <span className="nav-icon">
                      <Icon size={16} />
                    </span>
                    {l.label}
                  </NavLink>
                );
              })}
            </div>
          ))}
        </nav>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
