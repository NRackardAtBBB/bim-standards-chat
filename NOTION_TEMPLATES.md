# Sample Notion Standard Page Templates

Use these templates to create standards in your Notion database.

---

## Template 1: Workset Naming Convention

**Copy to Notion →**

```
Title: Workset Naming Convention
Category: Worksets
Studio: All Studios
Revit Version: 2023, 2024, 2025
Status: Active
Priority: Critical
Keywords: worksets, naming, organization, file-structure
```

**Page Content:**

```markdown
# Workset Naming Convention

## Overview
Consistent workset naming is critical for multi-user coordination, model organization, and file management across all BBB projects.

## When to Use
- All workshared Revit models
- From schematic design through construction documents
- Both architectural and coordination models

## Naming Format
Use this format: `[Discipline]-[Category]-[Subcategory]`

### Components
- **Discipline**: 1-3 letter prefix (A, S, MEP, etc.)
- **Category**: Major element group (SHELL, INTERIOR, FURNITURE)
- **Subcategory**: Specific element type (optional, use when needed)

## Standard Prefixes

### Architecture
- `A-` Architecture/Architectural
- `A-SHELL-` Building shell and envelope
- `A-INTERIOR-` Interior architecture
- `A-FURNITURE-` Furniture and equipment
- `A-SITE-` Site elements

### Structure
- `S-` Structure/Structural
- `S-GRID-` Grids and levels
- `S-FOUNDATION-` Foundations
- `S-FRAME-` Structural frame

### MEP
- `MEP-` Mechanical, Electrical, Plumbing
- `MEP-HVAC-` HVAC systems
- `MEP-PLUMBING-` Plumbing systems
- `MEP-ELECTRICAL-` Electrical systems

## Examples

### Good Examples ✅
- `A-SHELL-EXTERIOR`
- `A-SHELL-ROOF`
- `A-INTERIOR-PARTITIONS`
- `A-INTERIOR-DOORS`
- `A-INTERIOR-CASEWORK`
- `A-FURNITURE-FIXED`
- `S-STRUCTURE-COLUMNS`
- `S-STRUCTURE-BEAMS`
- `MEP-PLUMBING-FIXTURES`

### Bad Examples ❌
- `Walls` (too vague, no discipline)
- `arch_exterior_walls` (wrong format, lowercase)
- `A_Shell_Ext` (underscores, mixed case)
- `Architecture-Building-Exterior-Walls-and-Doors` (too long)

## Rules

1. **All uppercase letters**
2. **Use hyphens** for separators (NOT underscores)
3. **Discipline prefix first** (A, S, MEP, etc.)
4. **Maximum 30 characters** (Revit display limit)
5. **No special characters** except hyphens
6. **No spaces**
7. **Be specific but concise**

## Special Worksets

### Required System Worksets
- `Shared Levels and Grids` (default, Revit-created)
- `Views` (optional, for view-specific elements)

### Link Worksets
Format: `LINK-[Discipline]-[Source]`
- `LINK-S-STRUCTURAL` (structural link)
- `LINK-MEP-MECHANICAL` (MEP link)
- `LINK-A-SITEBLDG` (site building link)

## Project-Specific Worksets

For project-specific needs:
- Add project abbreviation at end: `A-INTERIOR-[PROJECT]`
- Example: `A-INTERIOR-ALTERATION-PHASE2`

## Common Issues

### Issue: Too many worksets
**Solution**: Combine related elements. Don't create workset per room.

### Issue: Inconsistent naming
**Solution**: Use this standard from day one. Don't change mid-project.

### Issue: Users forgetting which workset
**Solution**: Set default workset in template. Use Guardian to check.

## Related Standards
- Model Organization Standard
- File Naming Convention
- Guardian Workset Rules
- ACC/BIM 360 Structure

## Guardian Rules
The following Guardian rules enforce this standard:
- Workset naming pattern check
- Invalid character check
- Maximum length check

## Last Updated
January 2025 - Updated for Revit 2025 compatibility

## Questions?
Contact your studio BIM coordinator or DCT team.
```

---

## Template 2: View Template Usage

**Copy to Notion →**

```
Title: View Template Usage Guidelines
Category: Views
Studio: All Studios
Revit Version: 2023, 2024, 2025
Status: Active
Priority: Important
Keywords: views, templates, graphics, standards, documentation
```

**Page Content:**

```markdown
# View Template Usage Guidelines

## Overview
View templates ensure consistency in documentation appearance and save time by applying standard graphics settings.

## When to Use
- **All construction document views** (required)
- Presentation views (recommended)
- Coordination views (recommended)
- Working views (optional)

## Standard Templates

### Construction Documents

#### Floor Plans
- `CD-Floor Plan` - Standard floor plans
- `CD-Floor Plan-Enlarged` - Enlarged/detail plans
- `CD-Ceiling Plan` - Reflected ceiling plans

#### Sections & Elevations
- `CD-Section-Building` - Building sections
- `CD-Section-Wall` - Wall sections
- `CD-Elevation-Exterior` - Exterior elevations
- `CD-Elevation-Interior` - Interior elevations

#### Details
- `CD-Detail-Typical` - Standard details
- `CD-Detail-Enlarged` - Enlarged details at 3"=1'-0" or larger

### Working Views
- `WIP-Working View` - For modeling and coordination
- `WIP-Working 3D` - 3D working views

### Coordination
- `COORD-Coordination` - For consultant coordination
- `COORD-Clash Detection` - For interference checking

## How to Apply

### New Views
1. Create view (duplicate with detailing)
2. Right-click view in Project Browser
3. Select "Apply Template Properties"
4. Choose appropriate template from list
5. Click OK

### Existing Views
1. Select view in Project Browser
2. Right-click → Apply Template Properties
3. Choose template
4. Review any overrides needed

### Multiple Views
1. Select multiple views in Project Browser (Ctrl+Click)
2. Right-click → Apply Template Properties
3. Apply same template to all

## Template Settings

Templates control:
- ✅ View scale
- ✅ Detail level
- ✅ Visibility/Graphics overrides
- ✅ Line weights
- ✅ Halftone/Transparency
- ✅ Filters
- ✅ Graphic display options
- ✅ View depth
- ✅ Phase settings
- ✅ Underlay settings

## Customization Rules

### ❌ Never Do This
- Modify the base template directly
- Override template settings without approval
- Create project-specific templates without naming convention

### ✅ Do This Instead
- Use template as-is whenever possible
- Request template changes from DCT team
- Create project-specific override if needed (follow naming)

### Project-Specific Overrides
If needed, name as: `[Template Name]-[Project Code]`

Example:
- Base: `CD-Floor Plan`
- Project: `CD-Floor Plan-MET`

## Common Issues

### Issue: View doesn't look right after applying template
**Solution**: 
1. Check if view has local overrides (blue parameter values)
2. Reset overrides: View Properties → find blue values → click "reset"
3. Re-apply template

### Issue: Template is missing from list
**Solution**:
1. Check template file version matches project
2. Reload latest template file
3. Contact BIM coordinator if still missing

### Issue: Changes to template don't appear
**Solution**:
1. View templates update only when re-applied
2. Select views → Re-apply template
3. Or use "Update to changes in template" if prompted

## Template Maintenance

### For BIM Coordinators
- Review templates quarterly
- Test in current Revit version
- Document any customizations
- Share updates with team

### For Users
- Don't modify templates
- Report issues to BIM coordinator
- Suggest improvements based on workflow

## Related Standards
- View Naming Convention
- Sheet Composition Guidelines
- Line Weight Standards
- Phase Configuration

## Guardian Rules
- View template check for CD views
- Unapplied template warning
- Template naming pattern check

## Last Updated
January 2025

## Questions?
Contact your studio BIM coordinator.
```

---

## Template 3: Level Management

**Copy to Notion →**

```
Title: Level Management Standards
Category: Modeling
Studio: All Studios
Revit Version: 2023, 2024, 2025
Status: Active
Priority: Critical
Keywords: levels, datums, organization, coordination
```

**Page Content:**

```markdown
# Level Management Standards

## Overview
Proper level management is essential for model organization, coordination with consultants, and accurate documentation.

## Core Principles

1. **Levels are shared** - Affect entire project
2. **Levels define floor elevations** - Not every height change
3. **Levels drive views** - Plan and section views
4. **Levels coordinate** - Match consultant models

## When to Create Levels

### Do Create Levels For:
- ✅ Floor levels (ground floor, 2nd floor, etc.)
- ✅ Roof levels
- ✅ Significant grade changes
- ✅ Ceiling heights (if needed for coordination)
- ✅ Reference levels (T.O. parapet, etc.)

### Don't Create Levels For:
- ❌ Every wall height
- ❌ Temporary modeling purposes
- ❌ Individual room ceiling heights
- ❌ Minor elevation changes

## Naming Convention

### Format
`[Number] [Name]` or `[Name]`

### Examples - Multi-Story
- `G Ground Floor` or `L1 Ground Floor`
- `L2 Second Floor`
- `L3 Third Floor`
- `R1 Roof`

### Examples - Single Story
- `Ground Floor`
- `Ceiling`
- `Roof`

### Examples - Reference Levels
- `T.O. Parapet`
- `T.O. Penthouse`
- `Bottom of Foundation`

### Rules
- Start with floor number if multi-story
- Use consistent naming throughout project
- Don't rename levels mid-project
- Match consultant level names exactly

## Elevation Datum

### Set Correctly From Start
1. Coordinate with civil/survey
2. Set project base point elevation
3. Align level 1 with survey datum
4. Document in project setup

### Standard Practice
- Ground floor = 0' - 0" or match survey
- Verify with civil consultant
- Don't change once model is started

## Level Properties

### Settings to Configure
- **Name**: Follow naming convention
- **Elevation**: Accurate floor-to-floor
- **2D/3D Extents**: Control visibility in views
- **Scope Box**: Assign if using scope boxes
- **Workset**: `Shared Levels and Grids`

## Creating New Levels

### Method 1: Duplicate Existing
1. Open elevation or section
2. Select level
3. Right-click → Duplicate
4. Move to correct height
5. Rename appropriately

### Method 2: Draw New
1. Open elevation or section
2. Architecture tab → Level
3. Draw level line
4. Name immediately
5. Set elevation in properties

## Deleting Levels

### Before Deleting:
1. Check for elements hosted on level
2. Check for views associated with level
3. Check for scope boxes using level
4. Reassign elements if needed

### How to Delete:
1. Select level in elevation/section
2. Press Delete
3. Confirm deletion
4. Review model for errors

## Common Issues

### Issue: Duplicate level names
**Guardian Error**: "Duplicate level names detected"

**Solution**:
1. Never acceptable - must fix immediately
2. Rename or delete duplicate
3. Check for hidden/deleted levels
4. Purge unused if needed

### Issue: Level won't delete
**Cause**: Elements hosted on level or views using level

**Solution**:
1. Find hosted elements (walls, floors, etc.)
2. Change host level
3. Delete associated views or change view level
4. Then delete level

### Issue: Levels don't match consultants
**Cause**: Different datum or naming

**Solution**:
1. Coordinate in linking meeting
2. Adjust datum if early in project
3. Document differences if can't change
4. Use Copy/Monitor to track

## Coordination

### With Structural
- Match level names exactly
- Verify floor-to-floor heights
- Use Copy/Monitor to track changes
- Review coordination warnings regularly

### With MEP
- Share architectural levels
- Add ceiling levels if needed
- Coordinate for equipment heights
- Document any MEP-specific levels

## View Management

### Associated Views
Each level can have:
- Floor plan view
- Ceiling plan view
- Structural plan view (if applicable)

### View Naming
Match level name:
- Level: `L2 Second Floor`
- Plan: `L2 Second Floor`
- RCP: `L2 Second Floor RCP`

## Best Practices

1. **Establish levels early** in design
2. **Coordinate with all disciplines** before finalizing
3. **Don't change levels** once construction documents start
4. **Use scope boxes** to control level visibility
5. **Document level datum** in project setup notes
6. **Check consistency** in all views

## Related Standards
- Grid Management
- View Naming Convention
- Coordination Process
- Scope Box Usage

## Guardian Rules
- Duplicate level name check
- Level naming pattern check
- Unassociated level warning

## Last Updated
January 2025

## Questions?
Contact your studio BIM coordinator or DCT team.
```

---

## How to Use These Templates

1. **Copy entire template** including metadata fields
2. **Paste into new Notion page** in your BBB Revit Standards database
3. **Set properties** (Category, Status, etc.) using Notion's property system
4. **Customize content** for your specific standards
5. **Add images/screenshots** to clarify concepts
6. **Link related pages** to create documentation network

## Tips for Writing Good Standards

- ✅ **Be specific** - Give exact examples
- ✅ **Use visuals** - Screenshots, diagrams, before/after
- ✅ **Explain why** - Not just what, but reasoning
- ✅ **Cover common issues** - FAQ section
- ✅ **Link related standards** - Create connected documentation
- ✅ **Keep updated** - Note last update date
- ✅ **Test searchability** - Use keywords users would search

---

**Need more templates?** Follow this structure for any standard:
1. Overview (what is this?)
2. When to use (scenarios)
3. How to do it (step-by-step)
4. Examples (good and bad)
5. Rules (clear requirements)
6. Common issues (troubleshooting)
7. Related standards (links)
8. Guardian rules (if applicable)
