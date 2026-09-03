import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import Dashboard from "./modules/dashboard/Dashboard";
import ProjectsList from "./modules/projects/ProjectsList";
import CreateProject from "./modules/projects/CreateProject";
import ProjectDetail from "./modules/projects/ProjectDetail";
import HttpInspector from "./modules/http/HttpInspector";
import JsInspector from "./modules/js/JsInspector";
import ApiMapper from "./modules/api/ApiMapper";
import Parameters from "./modules/parameters/Parameters";
import AuthFlow from "./modules/authflow/AuthFlow";
import Analyzer from "./modules/analyzer/Analyzer";
import Diff from "./modules/diff/Diff";
import AccessControlWorkbench from "./modules/workbench/AccessControlWorkbench";
import Investigations from "./modules/investigations/Investigations";
import Findings from "./modules/investigations/Findings";
import InvestigationDetail from "./modules/investigations/InvestigationDetail";
import Report from "./modules/reports/Report";
import PracticeLabs from "./modules/practice/PracticeLabs";
import PracticeLab from "./modules/practice/PracticeLab";
import SkillMap from "./modules/skills/SkillMap";
import { useAuth } from "./auth/AuthContext";
import Login from "./auth/Login";
import Security from "./auth/Security";
import Surface from "./modules/surface/Surface";
import BundleVerifier from "./modules/evidence/BundleVerifier";
import History from "./modules/history/History";

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex h-screen items-center justify-center bg-vajra-bg text-sm text-slate-500">Loading Vajra...</div>;
  if (!user) return <Login />;
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/projects" element={<ProjectsList />} />
        <Route path="/projects/new" element={<CreateProject />} />
        <Route path="/projects/:id" element={<ProjectDetail />} />
        <Route path="/projects/:id/http" element={<HttpInspector />} />
        <Route path="/projects/:id/js" element={<JsInspector />} />
        <Route path="/projects/:id/api-map" element={<ApiMapper />} />
        <Route path="/projects/:id/parameters" element={<Parameters />} />
        <Route path="/projects/:id/auth-flow" element={<AuthFlow />} />
        <Route path="/projects/:id/surface" element={<Surface />} />
        <Route path="/projects/:id/analyzer" element={<Analyzer />} />
        <Route path="/projects/:id/diff" element={<Diff />} />
        <Route path="/projects/:id/access-control" element={<AccessControlWorkbench />} />
        <Route path="/projects/:id/investigations" element={<Investigations />} />
        <Route path="/projects/:id/investigations/:invId" element={<InvestigationDetail />} />
        <Route path="/projects/:id/findings" element={<Findings />} />
        <Route path="/projects/:id/history" element={<History />} />
        <Route path="/projects/:id/investigations/:invId/report" element={<Report />} />
        <Route path="/skills" element={<SkillMap />} />
        <Route path="/practice" element={<PracticeLabs />} />
        <Route path="/practice/:labId" element={<PracticeLab />} />
        <Route path="/account/security" element={<Security />} />
        <Route path="/evidence/verify" element={<BundleVerifier />} />
      </Routes>
    </Layout>
  );
}
