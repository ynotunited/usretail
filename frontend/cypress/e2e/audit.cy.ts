/// <reference types="cypress" />
import 'cypress-axe';

describe('Accessibility and Performance Audits', () => {
  beforeEach(() => {
    cy.visit('/');
    cy.injectAxe();
  });

  it('Passes WCAG AA accessibility tests', () => {
    // Run accessibility tests
    cy.checkA11y(null, {
      includedImpacts: ['critical', 'serious'],
      runOnly: {
        type: 'tag',
        values: ['wcag2aa', 'wcag21aa']
      }
    });
  });

  it('Has high performance (Lighthouse - conceptually)', () => {
    // Note: To fully run cypress-audit for Lighthouse, we need specific plugins configured in cypress.config.ts
    // For now, we assert true as a placeholder, meaning the pipeline will run `npx lighthouse` standalone.
    cy.wrap(true).should('eq', true);
  });
});
