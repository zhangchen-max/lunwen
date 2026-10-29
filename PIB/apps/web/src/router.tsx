import { createBrowserRouter } from 'react-router-dom';
import { ReleaseDetailPage } from './pages/ReleaseDetailPage';
import { ReleasesPage } from './pages/ReleasesPage';
import { NewRunPage } from './pages/NewRunPage';
import { RunSummaryPage } from './pages/RunSummaryPage';
import { SlicesPage } from './pages/SlicesPage';
import { CaseDetailPage } from './pages/CaseDetailPage';

export const router = createBrowserRouter([
  {
    path: '/releases',
    element: <ReleasesPage />,
  },
  {
    path: '/releases/:releaseId',
    element: <ReleaseDetailPage />,
  },
  {
    path: '/runs/new',
    element: <NewRunPage />,
  },
  {
    path: '/runs/:runId',
    element: <RunSummaryPage />,
  },
  {
    path: '/runs/:runId/slices',
    element: <SlicesPage />,
  },
  {
    path: '/runs/:runId/cases/:caseId',
    element: <CaseDetailPage />,
  },
  {
    path: '*',
    element: <ReleasesPage />,
  },
]);
