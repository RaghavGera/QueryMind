import { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import BootScreen from "./components/ui/BootScreen";
import WarpOverlay from "./motion/WarpOverlay";
import { AuthProvider } from "./auth/AuthProvider";

// Route-level code splitting: the 3D universe and smooth scrolling (marketing
// pages) never load inside /app, and the app never loads with the landing page.
const MarketingLayout = lazy(() => import("./components/layout/MarketingLayout"));
const Landing = lazy(() => import("./pages/Landing"));
const Product = lazy(() => import("./pages/Product"));
const Architecture = lazy(() => import("./pages/Architecture"));
const Developers = lazy(() => import("./pages/Developers"));
const SignInPage = lazy(() => import("./pages/SignInPage"));
const Privacy = lazy(() => import("./pages/Privacy"));

const AppLayout = lazy(() => import("./components/layout/AppLayout"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const SchemaPage = lazy(() => import("./pages/SchemaPage"));
const HistoryPage = lazy(() => import("./pages/HistoryPage"));
const SavedPage = lazy(() => import("./pages/SavedPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const ConnectPage = lazy(() => import("./pages/ConnectPage"));

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
      <Suspense fallback={<BootScreen />}>
        <Routes>
          <Route element={<MarketingLayout />}>
            <Route path="/" element={<Landing />} />
            <Route path="/product" element={<Product />} />
            <Route path="/architecture" element={<Architecture />} />
            <Route path="/developers" element={<Developers />} />
            <Route path="/signin" element={<SignInPage />} />
            <Route path="/privacy" element={<Privacy />} />
          </Route>

          <Route path="/app" element={<AppLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="schema" element={<SchemaPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="saved" element={<SavedPage />} />
            <Route path="connect" element={<ConnectPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </Suspense>
      <WarpOverlay />
      </AuthProvider>
    </BrowserRouter>
  );
}
