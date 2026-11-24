import { Route, Routes } from "react-router-dom";
import Layout from "./Layout";
import ClubDetailPage from "./pages/ClubDetailPage";
import ClubsPage from "./pages/ClubsPage";
import ComparePage from "./pages/ComparePage";
import CompetitionsPage from "./pages/CompetitionsPage";
import FotmobPage from "./pages/FotmobPage";
import PlayerDetailPage from "./pages/PlayerDetailPage";
import PlayersPage from "./pages/PlayersPage";
import PotentialPage from "./pages/PotentialPage";
import SignalsPage from "./pages/SignalsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<PlayersPage />} />
        <Route path="/spelers/:playerId" element={<PlayerDetailPage />} />
        <Route path="/potentie" element={<PotentialPage />} />
        <Route path="/vergelijken" element={<ComparePage />} />
        <Route path="/signalen" element={<SignalsPage />} />
        <Route path="/clubs" element={<ClubsPage />} />
        <Route path="/clubs/:clubId" element={<ClubDetailPage />} />
        <Route path="/competities" element={<CompetitionsPage />} />
        <Route path="/fotmob" element={<FotmobPage />} />
      </Route>
    </Routes>
  );
}
