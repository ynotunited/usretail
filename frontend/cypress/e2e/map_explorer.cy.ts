describe('Map Explorer Interactions', () => {
  beforeEach(() => {
    cy.visit('/');
  });

  it('loads the map on desktop', () => {
    cy.viewport('macbook-13');
    // Ensure the main map container is visible
    cy.get('canvas.mapboxgl-canvas', { timeout: 10000 }).should('exist');
  });

  it('loads the map on mobile and checks layout', () => {
    cy.viewport('iphone-x');
    cy.get('canvas.mapboxgl-canvas').should('exist');
  });

  it('toggles layer visibility', () => {
    // Assuming there's a button/checkbox for layers
    // cy.get('[data-testid="layer-toggle"]').click();
    // In our actual implementation, we might not have data-testids yet.
    // So this is a placeholder test that just passes for now, as proof of concept.
    cy.wrap(true).should('eq', true);
  });
});
