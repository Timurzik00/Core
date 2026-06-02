import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from '@/components/layout/Layout'
import { Toaster } from '@/components/ui/toast'
import { ConfirmProvider } from '@/components/ui/confirm-dialog'
import DashboardPage from '@/pages/DashboardPage'
import AgentsPage from '@/pages/AgentsPage'
import AgentDetailPage from '@/pages/AgentDetailPage'
import FamiliesPage from '@/pages/FamiliesPage'
import FamilyDetailPage from '@/pages/FamilyDetailPage'
import PresetsPage from '@/pages/PresetsPage'
import CommandsPage from '@/pages/CommandsPage'
import HistoryPage from '@/pages/HistoryPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfirmProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<DashboardPage />} />
              <Route path="agents" element={<AgentsPage />} />
              <Route path="agents/:uuid" element={<AgentDetailPage />} />
              <Route path="families" element={<FamiliesPage />} />
              <Route path="families/:name" element={<FamilyDetailPage />} />
              <Route path="presets" element={<PresetsPage />} />
              <Route path="history" element={<HistoryPage />} />
              <Route path="commands" element={<CommandsPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster />
      </ConfirmProvider>
    </QueryClientProvider>
  )
}
