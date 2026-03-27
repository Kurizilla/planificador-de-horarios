import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './AuthContext'
import Layout from './Layout'
import ProtectedRoute from './ProtectedRoute'
import Login from './pages/Login'
import Register from './pages/Register'
import ProjectList from './pages/ProjectList'
import ProjectNew from './pages/ProjectNew'
import UserManagement from './pages/UserManagement'
import DataImport from './pages/DataImport'
import ScheduleView from './pages/ScheduleView'
import './App.css'

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/projects" replace />} />
        <Route path="projects">
          <Route index element={<ProjectList />} />
          <Route path="new" element={<ProjectNew />} />
          <Route path=":id" element={<Navigate to="import" replace />} />
          <Route path=":id/import" element={<DataImport />} />
          <Route path=":id/schedule" element={<ScheduleView />} />
        </Route>
        <Route path="users" element={<UserManagement />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
