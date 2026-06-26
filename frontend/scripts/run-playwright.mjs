import { spawn } from 'node:child_process';
import net from 'node:net';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const vitePackageJson = require.resolve('vite/package.json');
const viteBin = path.join(path.dirname(vitePackageJson), 'bin', 'vite.js');
const playwrightCli = require.resolve('@playwright/test/cli');
const host = '127.0.0.1';
const port = 4173;

const waitForPort = (hostname, targetPort, timeoutMs = 30000) =>
  new Promise((resolve, reject) => {
    const startedAt = Date.now();

    const attempt = () => {
      const socket = net.createConnection({ host: hostname, port: targetPort });

      socket.once('connect', () => {
        socket.end();
        resolve();
      });

      socket.once('error', () => {
        socket.destroy();
        if (Date.now() - startedAt > timeoutMs) {
          reject(new Error(`Timed out waiting for ${hostname}:${targetPort}`));
          return;
        }
        setTimeout(attempt, 250);
      });
    };

    attempt();
  });

const server = spawn(process.execPath, [viteBin, '--host', host, '--port', String(port)], {
  stdio: 'inherit',
  windowsHide: true,
});

const stopServer = () => {
  if (!server.killed) {
    server.kill();
  }
};

process.on('exit', stopServer);
process.on('SIGINT', () => {
  stopServer();
  process.exit(130);
});
process.on('SIGTERM', () => {
  stopServer();
  process.exit(143);
});

try {
  await waitForPort(host, port);

  const playwright = spawn(process.execPath, [playwrightCli, 'test'], {
    stdio: 'inherit',
    windowsHide: true,
  });

  const exitCode = await new Promise((resolve, reject) => {
    playwright.once('error', reject);
    playwright.once('exit', (code, signal) => {
      if (signal) {
        reject(new Error(`Playwright exited with signal ${signal}`));
        return;
      }
      resolve(code ?? 1);
    });
  });

  process.exitCode = exitCode;
} finally {
  stopServer();
}
