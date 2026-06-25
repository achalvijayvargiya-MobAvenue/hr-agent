import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { isLoggedIn } from './lib/auth'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import LoginPage from './modules/auth/LoginPage'
import PositionsPage from './modules/positions/PositionsPage'
import PositionDetailPage from './modules/positions/PositionDetailPage'
import CandidatesPage from './modules/candidates/CandidatesPage'
import CandidateDetailPage from './modules/candidates/CandidateDetailPage'
import MatchesPage from './modules/matches/MatchesPage'
import SourcesPage from './modules/sources/SourcesPage'
import UsersPage from './modules/users/UsersPage'

const queryClient = new QueryClient()

function RootRedirect() {
  return isLoggedIn() ? <Navigate to="/positions" replace /> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/login" element={<LoginPage />} />

          <Route
            path="/positions"
            element={
              <ProtectedRoute>
                <Layout>
                  <PositionsPage />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/positions/:id"
            element={
              <ProtectedRoute>
                <Layout>
                  <PositionDetailPage />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/candidates"
            element={
              <ProtectedRoute>
                <Layout>
                  <CandidatesPage />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/candidates/:email"
            element={
              <ProtectedRoute>
                <Layout>
                  <CandidateDetailPage />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/sources"
            element={
              <ProtectedRoute>
                <Layout>
                  <SourcesPage />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/matches"
            element={
              <ProtectedRoute>
                <Layout>
                  <MatchesPage />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/users"
            element={
              <ProtectedRoute>
                <Layout>
                  <UsersPage />
                </Layout>
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
