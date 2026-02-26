import {
  AngularNodeAppEngine,
  createNodeRequestHandler,
  isMainModule,
  writeResponseToNodeResponse,
} from '@angular/ssr/node';
import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import { join } from 'node:path';

const browserDistFolder = join(import.meta.dirname, '../browser');

const app = express();
const angularApp = new AngularNodeAppEngine();

// Determine the backend URL:
// - In Docker Compose the service is called "backend" on port 8000
// - Locally (dev SSR) fall back to localhost:8000
const BACKEND_URL = process.env['BACKEND_URL'] ?? 'http://localhost:8000';

/**
 * Proxy all /api/v1/* requests to the FastAPI backend.
 * The path rewrite strips the /api/v1 prefix because FastAPI routes
 * are mounted at the root (root_path is metadata-only for Swagger UI).
 *
 * This must be registered BEFORE the Angular SSR handler so that API
 * requests are never handed to the Angular rendering engine.
 */
app.use(
  '/api/v1',
  createProxyMiddleware({
    target: BACKEND_URL,
    changeOrigin: true,
    pathRewrite: { '^/api/v1': '' },
  }),
);

/**
 * Serve static files from /browser
 */
app.use(
  express.static(browserDistFolder, {
    maxAge: '1y',
    index: false,
    redirect: false,
  }),
);

/**
 * Handle all other requests by rendering the Angular application.
 */
app.use((req, res, next) => {
  angularApp
    .handle(req)
    .then((response) =>
      response ? writeResponseToNodeResponse(response, res) : next(),
    )
    .catch(next);
});

if (isMainModule(import.meta.url) || process.env['pm_id']) {
  const port = process.env['PORT'] || 4000;
  app.listen(port, (error) => {
    if (error) {
      throw error;
    }

    console.log(`Node Express server listening on http://localhost:${port}`);
    console.log(`Proxying /api/v1/* → ${BACKEND_URL}/*`);
  });
}

export const reqHandler = createNodeRequestHandler(app);
