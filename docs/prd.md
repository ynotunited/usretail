Product Requirements Document (PRD)
U.S. Retail Site Selection Analysis Platform
Using QGIS for Geographic Intelligence & Business Decision-Making
1. Project Overview
Project Name

RetailIQ GIS: U.S. Retail Site Selection Analysis

Project Type

Geospatial Analysis Portfolio Project

Purpose

Develop a professional geospatial analysis project that identifies optimal locations for opening a new coffee shop in a U.S. metropolitan area using GIS techniques.

The project demonstrates proficiency in:

QGIS
Spatial Analysis
Buffer Analysis
Heat Mapping
Demographic Analysis
Site Suitability Modeling
Business Intelligence
2. Business Problem

Opening a retail location in the wrong area can result in:

Low customer traffic
High operational costs
Poor profitability

Businesses need data-driven methods to determine:

Where potential customers are located
Where competitors are located
Which locations are underserved
Which areas have high growth potential
3. Project Goal

Determine the Top 10 Locations in a U.S. city where a new coffee shop should be established.

4. Project Objectives
Objective 1

Identify areas with:

High population density
High foot traffic
High office concentration
Objective 2

Identify areas underserved by competitors.

Objective 3

Measure accessibility to:

Roads
Transit stations
Universities
Shopping centers
Objective 4

Create a suitability score for each potential location.

5. Target City

Choose one:

Recommended
Austin, Texas

or

Seattle, Washington

or

New York City

or

Chicago

Austin is recommended because:

Data availability
Tech growth
Simpler geography
6. User Personas
Persona 1

Retail Expansion Manager

Needs:

Best new store locations
Competitive intelligence
Persona 2

Franchise Owner

Needs:

High customer density
Low competition
Persona 3

Real Estate Analyst

Needs:

Investment opportunities
7. Geographic Datasets
Administrative Boundaries

Source:

U.S. Census Bureau

Data:

City Boundaries
Census Tracts
ZIP Codes
Population Data

Source:

U.S. Census

Data:

Population
Age Groups
Income Levels
Road Network

Source:

OpenStreetMap

Data:

Highways
Primary Roads
Secondary Roads
Transit Data

Source:

GTFS datasets

Data:

Bus Stops
Train Stations
Transit Routes
Competitor Locations

Source:

OpenStreetMap

Examples:

Starbucks
Dunkin'
Peet's Coffee
Points of Interest

Source:

OpenStreetMap

Examples:

Schools
Universities
Hospitals
Shopping Malls
Office Buildings
8. GIS Layers
Layer 1

City Boundary

Layer 2

Population Density

Layer 3

Median Income

Layer 4

Competitor Locations

Layer 5

Road Network

Layer 6

Transit Stations

Layer 7

Office Buildings

Layer 8

Universities

Layer 9

Shopping Centers

9. Analysis Modules
Module A

Population Density Analysis

Purpose:

Locate high-demand areas.

Method:

Choropleth Maps
Density Mapping

Output:

Population Hotspots

Module B

Income Analysis

Purpose:

Find areas with spending power.

Method:

Census Data Overlay

Output:

High-Income Zones

Module C

Competitor Analysis

Purpose:

Locate competitor saturation.

Method:

Point Mapping
Density Mapping

Output:

Competition Heatmap

Module D

Buffer Analysis

Purpose:

Measure influence zones.

Buffers:

500m

Walkable Distance

1km

Neighborhood Reach

3km

Extended Reach

Output:

Accessibility Zones

Module E

Transit Accessibility

Purpose:

Measure customer access.

Method:

Distance to Transit Stops

Output:

Transit Accessibility Score

Module F

Road Accessibility

Purpose:

Evaluate visibility and access.

Method:

Road Proximity Analysis

Output:

Traffic Exposure Score

10. Suitability Model

Weighted Overlay Analysis

Formula:

Suitability Score =
(Population Density × 30%)
+
(Income Level × 25%)
+
(Transit Access × 15%)
+
(Road Access × 15%)
+
(Competitor Gap × 15%)
11. AI Component

Use AI for:

Competitor Insights

Prompt:

Analyze competitor density and identify underserved regions.

Site Recommendations

Prompt:

Based on GIS outputs, rank the best coffee shop locations.

Automated Reporting

Generate:

Executive Summary
Recommendations
Risk Assessment
12. Dashboard Deliverables
Map 1

Population Density Heatmap

Map 2

Income Distribution Map

Map 3

Competitor Locations

Map 4

Transit Accessibility Map

Map 5

Site Suitability Map

Map 6

Top Recommended Locations

13. Portfolio Screenshots

Capture:

Screenshot 1

Raw GIS Layers

Screenshot 2

Buffer Analysis

Screenshot 3

Competitor Analysis

Screenshot 4

Suitability Model

Screenshot 5

Final Recommendation Map

14. Technical Stack
GIS
QGIS
Data Sources
OpenStreetMap
U.S. Census Bureau
Database (Optional)
PostgreSQL
PostGIS
Frontend (Optional)
React
Next.js
Leaflet
15. Success Criteria

The project is successful when it can:

✅ Import and manage GIS datasets

✅ Perform spatial analysis

✅ Execute buffer analysis

✅ Generate heatmaps

✅ Analyze competitor locations

✅ Produce suitability rankings

✅ Recommend top retail locations

✅ Deliver professional GIS maps suitable for a portfolio