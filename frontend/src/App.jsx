import { BrowserRouter, Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import Product from "./pages/Product";
import Architecture from "./pages/Architecture";
import Developers from "./pages/Developers";
import AppLayout from "./components/layout/AppLayout";
import Dashboard from "./pages/Dashboard";
import SchemaPage from "./pages/SchemaPage";
import HistoryPage from "./pages/HistoryPage";
import SavedPage from "./pages/SavedPage";
import SettingsPage from "./pages/SettingsPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/product" element={<Product />} />
        <Route path="/architecture" element={<Architecture />} />
        <Route path="/developers" element={<Developers />} />

        <Route path="/app" element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="schema" element={<SchemaPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="saved" element={<SavedPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
