# NetWORKS Visual Design Specification
## Plugins - Docked Panels & Windows

> **Design Philosophy**: Compact, feature-rich, and modern with Microsoft Office-inspired interface patterns. Plugins should blend seamlessly with the main application while maintaining functional density.

---

## 1. Color System

### Primary Palette

**Aruba Orange (Muted)**
- **Primary**: `#E87722` (RGB 232, 119, 34)
- **Hover**: `#D66A1F` (10% darker)
- **Pressed**: `#C35E1C` (15% darker)
- **Disabled**: `#E8772240` (25% opacity)

**Configuration:**
- Accent color is configurable in settings; Aruba orange is the default.

**Usage:**
- Primary action buttons
- Selection highlights
- Active tab indicators
- Focus states
- Links and interactive elements

### Neutral Palette

**Light Theme:**
- **Background**: `#FFFFFF`
- **Surface**: `#F8F9FA`
- **Border**: `#D1D5DB`
- **Text Primary**: `#1F2937`
- **Text Secondary**: `#6B7280`
- **Text Disabled**: `#9CA3AF`

**Dark Theme:**
- **Background**: `#1E1E1E`
- **Surface**: `#2D2D2D`
- **Border**: `#3E3E3E`
- **Text Primary**: `#E5E7EB`
- **Text Secondary**: `#9CA3AF`
- **Text Disabled**: `#6B7280`

### Semantic Colors

**Success**: `#10B981` (Green)
**Warning**: `#F59E0B` (Amber)
**Error**: `#EF4444` (Red)
**Info**: `#3B82F6` (Blue)

---

## 2. Typography

### Font System

**Primary Font**: System default (Segoe UI on Windows, San Francisco on macOS)

**Font Sizes:**
- **Large**: Base + 2pt (Panel titles, dialog headers)
- **Normal**: Base (Body text, labels, table content)
- **Small**: Base - 1pt (Helper text, metadata, timestamps)
- **Tiny**: Base - 2pt (Status bar, secondary metadata)

**Font Weights:**
- **Bold**: 600 - Section headers, emphasis
- **Semi-bold**: 500 - Panel titles, tab labels
- **Regular**: 400 - Body text, labels
- **Light**: 300 - Not recommended (readability)

**Monospace Font**: Consolas, Monaco, Courier New
- Use for: IP addresses, MAC addresses, IDs, logs, code snippets
- Example: `192.168.1.1`, `AA:BB:CC:DD:EE:FF`

---

## 3. Spacing System

### Grid: 4px Base Unit

**Standard Increments:**
- **2px**: Icon padding, minimal gaps
- **4px**: Tight spacing, inline elements
- **8px**: Standard element spacing, padding
- **12px**: Section spacing, panel padding
- **16px**: Major section breaks
- **24px**: Large section breaks, dialog margins

**Component Spacing:**
- Cell padding: 4px horizontal, 2px vertical
- Form element spacing: 8px vertical
- Section spacing: 12-16px vertical
- Panel padding: 8-12px all sides
- Dialog padding: 16-24px all sides

---

## 4. Plugin Dock Panels

### Panel Structure

```
┌──────────────────────────────────────────┐
│ [Icon] Panel Title              [▼] [×]  │ ← Header: 28px
├──────────────────────────────────────────┤
│ ┌─ Section 1 ────────────────────────┐  │
│ │ Content...                          │  │
│ └─────────────────────────────────────┘  │ ← Padding: 8px
│ ┌─ Section 2 ────────────────────────┐  │
│ │ Content...                          │  │
│ └─────────────────────────────────────┘  │
│                                          │
│ Status info | 12 items | Updated 2m ago │ ← Footer: 24px
└──────────────────────────────────────────┘
```

### Header Design

**Structure:**
- Height: 28px fixed
- Background: Surface color
- Bottom border: 1px solid border color
- Padding: 6px horizontal, 12px bottom

**Elements:**
- **Icon** (optional): 16×16px, 4px from left edge
- **Title**: Semi-bold, normal size, 6px from icon
- **Title text**: Use the plugin name so the docked panel is easy to identify
- **Actions**: Right-aligned, 2px spacing between icons
  - Common: Collapse (▼), Settings (⚙), Close (×)
  - Icon size: 16×16px
  - Click area: 20×20px minimum

**Example:**
```
┌──────────────────────────────────────────┐
│ [📊] Device Statistics          [▼] [×]  │
└──────────────────────────────────────────┘
```

### Content Area

**Organization:**
Use collapsible sections for organization:

```
┌─ Quick Actions ─────────────────────────┐
│ [Start Scan] [Refresh] [Export]         │
└──────────────────────────────────────────┘

┌─ Filters ▼──────────────────────────────┐
│ Status:  [All Devices        ▼]         │
│ Type:    [All Types          ▼]         │
└──────────────────────────────────────────┘

┌─ Results (24) ──────────────────────────┐
│ Name          IP            Status      │
├──────────────────────────────────────────┤
│ Router        192.168.1.1   ● Online    │
│ Switch        192.168.1.2   ● Online    │
└──────────────────────────────────────────┘
```

**Section Headers:**
- Height: 24px
- Font: Semi-bold, normal size
- Background: Slightly darker than surface
- Border: 1px solid border color
- Padding: 4px horizontal, 12px bottom
- Collapse indicator: ▼ (expanded) / ▶ (collapsed)
- Click entire header to expand/collapse

**Content Padding:**
- Inside sections: 8px all sides
- Between sections: 4px vertical gap
- Between elements in section: 4px-8px

### Footer (Status Bar)

**Structure:**
- Height: 24px
- Background: Surface color
- Top border: 1px solid border color
- Padding: 4px horizontal
- Font: Small size, secondary text color

**Content:**
- Multiple segments separated by "|"
- Left-aligned status messages
- Right-aligned metadata (counts, timestamps)
- Use icons (12×12px) for visual indicators

**Example:**
```
Ready | 24 devices | Last scan: 2m ago
```

### Sizing

**Dimensions:**
- Minimum width: 200px
- Default width: 300px
- Recommended max width: 500px
- Minimum height: 150px
- User-resizable: Yes
- Remember size: Yes (per workspace)

---

## 5. Plugin Popup Windows

### Settings Dialog

```
┌──────────────────────────────────────────┐
│ Plugin Name - Settings           [_][□][×]│ ← Title bar: 32px
├──────────────────────────────────────────┤
│ [General] [Advanced] [Network] [About]   │ ← Tabs: 32px
├──────────────────────────────────────────┤
│                                          │
│ ┌─ Connection Settings ─────────────┐   │
│ │ Server:    [192.168.1.1       ]   │   │
│ │ Port:      [8080              ]   │   │
│ │ Timeout:   [30      ] seconds      │   │
│ │                                    │   │
│ │ ☑ Auto-connect on startup          │   │
│ │ ☐ Retry on failure                 │   │
│ └────────────────────────────────────┘   │
│                                          │
│ ┌─ Display Options ──────────────────┐   │
│ │ Theme:     [Auto            ▼]     │   │
│ │ Density:   [Compact         ▼]     │   │
│ │                                    │   │
│ │ ☑ Show tooltips                    │   │
│ │ ☑ Enable animations                │   │
│ └────────────────────────────────────┘   │
│                                          │
│                [Cancel] [Apply] [OK]     │ ← Button bar: 40px
└──────────────────────────────────────────┘
```

**Dialog Specifications:**

**Window:**
- Minimum size: 500×400px
- Default size: 600×500px
- Resizable: Yes
- Modal: Yes
- Remember position: Yes

**Title Bar:**
- Height: 32px
- System standard controls (minimize, maximize, close)
- Title: Bold, normal size

**Tab Bar:**
- Height: 32px
- Tab padding: 12px horizontal, 6px vertical
- Active tab: Border bottom 2px solid orange, bold text
- Inactive tab: No border, regular text
- Tab hover: Subtle background change

**Content Area:**
- Padding: 16px all sides
- Section spacing: 12px between sections
- Section padding: 8px inside sections
- Scrollable if content exceeds height
- Group box titles should include 12px of bottom padding so the text
   does not sit flush against the border.

**Button Bar:**
- Height: 40px minimum
- Background: Slightly darker than content
- Top border: 1px solid border color
- Padding: 8px horizontal
- Buttons: Right-aligned, 8px spacing
- Button order: Cancel, Apply, OK (left to right)

### Data/Results Dialog

```
┌──────────────────────────────────────────┐
│ Scan Results - 192.168.1.0/24    [_][□][×]│
├──────────────────────────────────────────┤
│                                          │
│ ┌────────────────────────────────────┐  │
│ │ Name      │ IP Address  │ Status   │  │
│ ├───────────┼─────────────┼──────────┤  │
│ │ Router    │ 192.168.1.1 │ ● Online │  │
│ ├───────────┼─────────────┼──────────┤  │
│ │ Switch    │ 192.168.1.2 │ ● Online │  │
│ ├───────────┼─────────────┼──────────┤  │
│ │ Printer   │ 192.168.1.15│ ● Online │  │
│ ├───────────┼─────────────┼──────────┤  │
│ │ Desktop   │ 192.168.1.50│ ○ Offline│  │
│ └────────────────────────────────────┘  │
│                                          │
│ 12 devices found | 11 online, 1 offline  │
│                                          │
│        [Export CSV] [Add All] [Close]   │
└──────────────────────────────────────────┘
```

**Specifications:**
- Minimum size: 600×400px
- Padding: 16px
- Status text: Small size, secondary color
- Tables: Full cell borders (see table section)

### Progress Dialog

```
┌──────────────────────────────────────────┐
│ Scanning Network...              [_][□][×]│
├──────────────────────────────────────────┤
│                                          │
│            [Spinner 32×32px]             │
│                                          │
│        Scanning 192.168.1.0/24           │
│                                          │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░ 65%        │
│                                          │
│ Devices found: 12 | Time: 00:12          │
│                                          │
│                     [Cancel]             │
└──────────────────────────────────────────┘
```

**Specifications:**
- Size: 400×250px (not resizable)
- Center on parent
- Content centered vertically
- Progress bar: Height 8px, rounded ends
- Spinner: 32×32px, accent color

---

## 6. UI Components

### Buttons

**Primary Button:**
```
┌─────────────┐
│  Start Scan │  ← Orange fill, white text
└─────────────┘
```
- Background: `#E87722`
- Text: White
- Height: 28px
- Padding: 12px horizontal, 6px vertical
- Border: 1px solid border color (visible outline)
- Corner radius: 0px (sharp)
- Font: Semi-bold

**Secondary Button:**
```
┌─────────────┐
│   Cancel    │  ← Border, no fill
└─────────────┘
```
- Background: Transparent
- Border: 1px solid border color
- Text: Primary text color
- Same dimensions as primary

**Danger Button:**
```
┌─────────────┐
│   Delete    │  ← Red fill
└─────────────┘
```
- Background: `#EF4444`
- Text: White
- Same dimensions as primary
 - Border: 1px solid border color (visible outline)

**Icon Button (Toolbar):**
```
┌────┐
│ 🔍 │  24×24px icon
│Scan│  Label below
└────┘
```
- Size: 24×24px icon
- Label: Small font, centered below
- Responsive: If label would truncate, hide it and show icon-only with tooltip
- Padding: 4px
- Total click area: 32×32px minimum
- Border: 1px solid border color (visible outline)
- Hover: Light background highlight

**States:**
- Hover: Background 10% lighter/darker
- Active: Background 15% lighter/darker
- Disabled: 40% opacity
- Focus: 2px orange outline

### Input Fields

**Text Input:**
```
Server: [192.168.1.1                    ]
        ↑ 8px spacing
```
- Height: 24px
- Padding: 4px horizontal, 2px vertical
- Border: 1px solid border color
- Corner radius: 0px
- Background: Background color
- Focus: 2px border orange

**Dropdown/Combo Box:**
```
Type: [All Devices                    ▼]
```
- Same as text input
- Dropdown arrow: 12×12px, 4px from right edge
- Dropdown list: Matches width, max height 200px

**Checkbox:**
```
☑ Auto-scan on startup
```
- Size: 16×16px
- Border: 1px solid border color
- Checked: Orange fill with white checkmark
- Label spacing: 6px from checkbox
- Label background: Transparent (no highlight)

**Radio Button:**
```
● Option 1
○ Option 2
```
- Size: 16×16px
- Same styling as checkbox

**Slider:**
```
Timeout: ├────●──────────┤ 5s
```
- Track height: 4px
- Handle: 12×12px circle
- Track fill: Orange (left of handle)
- Track empty: Border color

### Tables

**Compact Style with Borders:**

```
┌──────────┬─────────────┬──────────┐
│ Name     │ IP Address  │ Status   │ ← Header
├──────────┼─────────────┼──────────┤
│ Router   │ 192.168.1.1 │ ● Online │ ← Row 1 (bg)
├──────────┼─────────────┼──────────┤
│ Switch   │ 192.168.1.2 │ ● Online │ ← Row 2 (alt bg)
├──────────┼─────────────┼──────────┤
│ Printer  │ 192.168.1.15│ ○ Offline│
└──────────┴─────────────┴──────────┘
```

**Specifications:**

**Header:**
- Height: 24px
- Font: Semi-bold
- Background: Surface color (darker than table)
- Border: 1px solid border color (all sides)
- Cell padding: 4px horizontal, 2px vertical
- Sortable: Arrow indicator (▲▼) 8×8px

**Rows:**
- Height: 22px (compact)
- Cell padding: 4px horizontal, 2px vertical
- Borders: 1px solid border color (all cells)
- Alternating: Every other row 3% darker/lighter background
- Hover: 5% darker/lighter background
- Selected: Orange background 15% opacity

**Columns:**
- Minimum width: 60px
- Resizable: Drag border between headers
- Icon columns: Fixed 32px width
- Text: Left-aligned for text, right for numbers
- Monospace: For IPs, MACs, IDs

### Status Indicators

**Dot Indicators:**
```
● Online   ○ Offline   ◐ Connecting   ⊗ Error
```
- Size: 10px
- Colors: Success (online), border-only (offline), warning (connecting), error
- Spacing: 4px from text

**Badge Labels:**
```
[Online]  [Pending]  [Failed]
```
- Height: 18px
- Padding: 4px horizontal
- Border radius: 0px (sharp)
- Background: Semantic color at 15% opacity
- Text: Semantic color at full opacity
- Font: Small, semi-bold

### Icons

**Sizes:**
- Toolbar: 24×24px
- Panel header: 16×16px
- Inline: 16×16px
- Status: 12×12px
- Large (dialogs): 32×32px

**Style:**
- Solid/filled style (Material Icons)
- Monochrome (use theme text colors; black in light theme, white in dark theme)
- Minimal detail
- 2px stroke width when using outlines
- Format: SVG preferred

**Common Icons:**
- Play/Start: ▶
- Pause: ⏸
- Stop: ⏹
- Refresh: ↻
- Settings: ⚙
- Close: ×
- Collapse: ▼
- Expand: ▶
- Search: 🔍
- Add: +
- Remove: −
- Delete: 🗑

---

## 7. Plugin Toolbar Integration

### Ribbon Tab

When a plugin adds a ribbon tab, follow this structure:

```
┌─────────────────────────────────────────────────────────┐
│ [Plugin Name]                                           │ ← Tab label
├─────────────────────────────────────────────────────────┤
│ ┌─ Actions ─────┐ ┌─ Tools ──────┐ ┌─ View ─────┐     │
│ │ [▶]  [⏸] [⏹] │ │ [⚙] [↻] [🔍] │ │ [□] [═] [≡]│     │
│ │ Start Pause   │ │ Set Ref Find │ │ Grid List  │     │
│ │       Stop    │ │                │ │ Compact    │     │
│ └───────────────┘ └────────────────┘ └────────────┘     │
└─────────────────────────────────────────────────────────┘
```

**Tab Structure:**
- Tab height: 24px
- Tab padding: 8px horizontal
- Active indicator: 3px orange bar at bottom
- Font: Semi-bold when active

**Ribbon Groups:**
- Group header: Small font, secondary color, 6px padding
- Group border: 1px solid border color
- Group padding: 8px
- Spacing between groups: 8px

**Ribbon Buttons:**
- Icon: 24×24px
- Label: Small font, centered below icon
- Layout: Vertical (icon over label)
- Padding: 6px
- Minimum click area: 40×40px
- Large buttons: 32×32px icon, normal font label

### Context Menu

```
┌──────────────────────┐
│ Connect             │
│ Disconnect          │
├──────────────────────┤
│ Refresh             │
│ Properties...       │
├──────────────────────┤
│ ▶ Advanced          │ ← Submenu indicator
│ Delete         Del  │ ← Keyboard shortcut
└──────────────────────┘
```

**Specifications:**
- Item height: 24px
- Item padding: 8px horizontal, 4px vertical
- Icon size: 16×16px, 8px from left
- Keyboard shortcut: Small font, right-aligned
- Separator: 1px line, 4px margin top/bottom
- Submenu arrow: ▶ 8×8px
- Hover: Subtle background highlight

---

## 8. Common Patterns

### Collapsible Sections

**Collapsed:**
```
┌─ Filters ▶──────────────────────────────┐
└──────────────────────────────────────────┘
```

**Expanded:**
```
┌─ Filters ▼──────────────────────────────┐
│ Status:  [All Devices        ▼]         │
│ Type:    [All Types          ▼]         │
│ Group:   [All Groups         ▼]         │
└──────────────────────────────────────────┘
```

**Design:**
- Header: 24px height, clickable
- Indicator: ▶ (collapsed) / ▼ (expanded), 8×8px
- Content padding: 8px when expanded
- Animate: 150ms expand/collapse

### Empty States

```
┌──────────────────────────────────────────┐
│                                          │
│              [Icon 48×48px]              │
│                                          │
│           No Devices Found               │
│                                          │
│      Click "Start Scan" to discover      │
│         devices on your network          │
│                                          │
│            [Start Scan]                  │
│                                          │
└──────────────────────────────────────────┘
```

**Design:**
- Center content vertically and horizontally
- Icon: 48×48px, secondary color
- Heading: Normal font, semi-bold
- Description: Small font, secondary color, max 2 lines
- Action button: Optional, primary button style

### Loading States

**Spinner:**
```
[◐] Loading devices...
```
- Size: 16×16px (inline), 32×32px (centered)
- Color: Orange
- Animation: 1s rotation

**Progress Bar:**
```
Loading... ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░ 50%
```
- Height: 6px
- Fill: Orange
- Background: Border color
- Percentage: Small font, right of bar

**Skeleton:**
```
┌──────────────────────────────────────────┐
│ ░░░░░░░░  ░░░░░░░░░░░  ░░░░░░░          │
│ ░░░░░░░░  ░░░░░░░░░░░  ░░░░░░░          │
└──────────────────────────────────────────┘
```
- Use for table rows while loading
- Animated shimmer effect
- Match actual content layout

---

## 9. Accessibility

### Keyboard Navigation

**Required:**
- Tab: Move between controls
- Shift+Tab: Move backward
- Enter: Activate button/item
- Space: Toggle checkbox/radio
- Arrow keys: Navigate lists/trees
- Escape: Close dialog/cancel operation
- F1: Show help (if available)

**Focus Indicators:**
- Style: 2px solid orange outline
- Offset: 2px from element
- Visible on all focusable elements
- Never remove or hide

### Screen Readers

**Labels:**
- All inputs must have associated labels
- Icon buttons must have aria-label
- Status indicators must have text alternatives
- Progress must announce percentage

**Live Regions:**
- Status updates (aria-live="polite")
- Error messages (aria-live="assertive")
- Loading states (aria-busy="true")

### Visual Contrast

**Minimum Ratios:**
- Normal text: 4.5:1
- Large text: 3:1
- UI components: 3:1
- Active vs inactive: Clearly distinguishable

**Testing:**
- Test with Windows High Contrast mode
- Verify all states are visible
- Ensure text is readable at 200% zoom

---

## 10. Best Practices

### ✅ DO:

**Visual Consistency:**
- Use theme colors exclusively (no hardcoded colors)
- Follow the 4px grid system for all spacing
- Use system fonts with specified weights
- Match component styling to examples
- Test in both light and dark themes

**Information Density:**
- Pack information efficiently (compact style)
- Use collapsible sections to hide complexity
- Group related controls visually
- Use tabs for complex settings (4+ sections)
- Provide keyboard shortcuts for common actions

**User Experience:**
- Show loading states for all async operations
- Provide clear error messages with solutions
- Remember user preferences and window positions
- Enable full keyboard navigation
- Include tooltips on all toolbar buttons
- Support Ctrl+F for find-in-table

**Polish:**
- Use subtle animations (150-250ms)
- Provide empty states with helpful guidance
- Include status bar information
- Show timestamps with relative time ("2m ago")
- Display operation progress when possible

### ❌ DON'T:

**Visual Inconsistency:**
- Mix different button styles
- Use custom colors outside the theme
- Ignore spacing guidelines
- Create custom controls that don't match
- Use rounded corners (keep sharp)

**Cluttered Interface:**
- Show all options at once (use progressive disclosure)
- Use large padding/margins (keep compact)
- Include unnecessary decoration
- Repeat information unnecessarily
- Use oversized icons

**Poor UX:**
- Block the entire UI unnecessarily
- Show errors without guidance
- Use modal dialogs excessively
- Forget to show loading indicators
- Hide important actions in menus
- Make users memorize options

**Technical Issues:**
- Hardcode colors or fonts
- Ignore theme changes
- Break keyboard navigation
- Use inaccessible controls
- Forget to handle errors
- Leave debug logging enabled

---

## 11. Plugin Checklist

Before submitting a plugin, verify all items:

### Visual Design
- [ ] Uses theme colors (no hardcoded values)
- [ ] Works correctly in light theme
- [ ] Works correctly in dark theme
- [ ] Follows 4px spacing grid throughout
- [ ] Uses correct font sizes and weights
- [ ] Sharp corners on all buttons/inputs
- [ ] Icons are 24×24px in toolbar, 16×16px elsewhere
- [ ] Configured accent color used for primary actions
- [ ] Tables have cell borders and alternating rows
- [ ] Monospace font used for IPs, MACs, IDs

### Dock Panel
- [ ] Header is 28px with title and actions
- [ ] Content padding is 8-12px
- [ ] Uses collapsible sections for organization
- [ ] Footer shows relevant status information
- [ ] Panel is resizable (200px minimum width)
- [ ] Panel remembers size between sessions
- [ ] Scrolls properly when content is tall
- [ ] Blends with main window (no card look)

### Popup Windows
- [ ] Minimum size 500×400px for settings
- [ ] Uses tabs for complex settings (4+ sections)
- [ ] Standard title bar with system controls
- [ ] Content padding is 16px
- [ ] Action buttons right-aligned at bottom
- [ ] Primary action is rightmost button
- [ ] Window remembers position
- [ ] Closes with Escape key

### UI Components
- [ ] Buttons use correct colors and sizing
- [ ] Inputs are 24px height with 4px padding
- [ ] Dropdowns show arrow indicator
- [ ] Checkboxes are 16×16px with 6px label spacing
- [ ] Tables show full borders on all cells
- [ ] Status indicators use appropriate colors
- [ ] Icons are monochrome and solid style

### Functionality
- [ ] Full keyboard navigation works
- [ ] Tab order is logical
- [ ] Focus indicators are visible (2px orange)
- [ ] All icon buttons have tooltips
- [ ] Loading states show for async operations
- [ ] Error messages are clear and actionable
- [ ] Progress dialogs show percentage
- [ ] Empty states provide helpful guidance

### Accessibility
- [ ] All inputs have labels
- [ ] Icon buttons have aria-labels
- [ ] Keyboard shortcuts documented
- [ ] Contrast ratios meet WCAG AA
- [ ] Works with screen readers
- [ ] Tested at 125% and 150% zoom
- [ ] High contrast mode supported

### Polish
- [ ] No console errors or warnings
- [ ] Animations are subtle (150-250ms)
- [ ] Status bar shows helpful information
- [ ] Timestamps use relative format
- [ ] Settings persist between sessions
- [ ] Help/documentation available
- [ ] Plugin icon provided (48×48px minimum)

---

## 12. Example: Network Scanner Plugin

### Dock Panel - Compact Design

```
┌──────────────────────────────────────────┐
│ [🔍] Network Scanner            [▼] [×]  │ 28px header
├──────────────────────────────────────────┤
│ ┌─ Quick Scan ▼──────────────────────┐  │
│ │ Subnet: [192.168.1.0/24      ]     │  │
│ │ ☑ Include offline                  │  │
│ │ [Start Scan]                        │  │
│ └─────────────────────────────────────┘  │ 8px padding
│ ┌─ Results (8) ▼──────────────────────┐  │
│ │┌──────┬─────────────┬─────────────┐│  │
│ ││ Name │ IP Address  │ Status      ││  │
│ │├──────┼─────────────┼─────────────┤│  │
│ ││Router│ 192.168.1.1 │ ● Online    ││  │
│ │├──────┼─────────────┼─────────────┤│  │
│ ││Switch│ 192.168.1.2 │ ● Online    ││  │
│ │├──────┼─────────────┼─────────────┤│  │
│ ││Print │ 192.168.1.15│ ○ Offline   ││  │
│ │└──────┴─────────────┴─────────────┘│  │
│ └─────────────────────────────────────┘  │
│                                          │
│ Last scan: 5m ago | 8 found   [Details] │ 24px footer
└──────────────────────────────────────────┘
```

### Settings Dialog - Tabbed

```
┌──────────────────────────────────────────┐
│ Network Scanner - Settings      [_][□][×]│ 32px title
├──────────────────────────────────────────┤
│ [General] [Advanced] [Network] [About]   │ 32px tabs
├──────────────────────────────────────────┤
│                                          │
│ ┌─ Scan Configuration ───────────────┐  │
│ │ Default subnet:                    │  │
│ │ [192.168.1.0/24               ]    │  │
│ │                                    │  │
│ │ Timeout:   [5     ] seconds        │  │
│ │ Threads:   [100   ] threads        │  │
│ │ Port range:[1 ] to [65535    ]     │  │
│ │
│ │ Port range:[1 ] to [65535    ]     │  │
│ │ Port range:[1 ] to [65535    ]     │  │
│ │                                    │  │
│ │ ☑ Auto-scan on startup             │  │
│ │ ☐ Continuous scanning              │  │
│ └────────────────────────────────────┘  │
│                                          │
│ ┌─ Display ──────────────────────────┐  │
│ │ ☑ Show device icons                │  │
│ │ ☑ Group by subnet                  │  │
│ │ ☐ Show MAC addresses               │  │
│ └────────────────────────────────────┘  │
│                                          │ 16px padding
│         [Restore Defaults] [Cancel] [OK]│ 40px button bar
└──────────────────────────────────────────┘
```
Results Dialog - Data Table
┌──────────────────────────────────────────┐
│ Scan Results - 192.168.1.0/24    [_][□][×]│
├──────────────────────────────────────────┤
│ ┌────────┬─────────────┬──────────────┐ │
│ │ Name   │ IP Address  │ MAC Address  │ │ Headers
│ ├────────┼─────────────┼──────────────┤ │
│ │ Router │ 192.168.1.1 │ AA:BB:CC:... │ │ Row (bg)
│ ├────────┼─────────────┼──────────────┤ │
│ │ Switch │ 192.168.1.2 │ DD:EE:FF:... │ │ Alt row
│ ├────────┼─────────────┼──────────────┤ │
│ │ Printer│ 192.168.1.15│ 11:22:33:... │ │
│ ├────────┼─────────────┼──────────────┤ │
│ │ Desktop│ 192.168.1.50│ 44:55:66:... │ │
│ └────────┴─────────────┴──────────────┘ │
│                                          │
│ 8 devices | 7 online, 1 offline          │ Status
│                                          │
│        [Export CSV] [Add All] [Close]    │ Actions
└──────────────────────────────────────────┘


README.md
172 lines

md

Here is a README to a project I am working on. Are you able to help me spec out some design considerations for the plugins that are going into this?

9:17 PM
I'd be happy to help you spec out design considerations for your NetWORKS plugin system! Based on the README, you've already got a solid foundation with the plugin architecture.

Let me ask a few questions to better understand what you're looking for:

Scope: Are you looking for design considerations for:
The plugin API/interface itself (what plugins can do)?
Specific types of plugins you're planning to build?
Plugin isolation and sandboxing?
Plugin communication and dependencies?
All of the above?
Current State: Have you already implemented the basic plugin system, or are you still in the design phase? The README mentions a sample plugin exists.
Priority Areas: Are there specific challenges or concerns you're facing? For example:
Plugin stability (preventing plugins from crashing the main app)?
Performance (lazy loading, resource management)?
Security (what plugins should/shouldn't access)?
Plugin discoverability and distribution?
In the meantime, here are some high-level design considerations I'd recommend thinking about based on what I see in your README:

Plugin Lifecycle & Loading

Lazy loading vs. eager loading strategies
Hot reload/unload without restarting the app
Dependency resolution between plugins
Graceful degradation when plugins fail
Plugin Capabilities & Boundaries

Clear API contracts for what plugins can access
Resource limits (memory, CPU, network)
File system access scope
Database/storage isolation per plugin
UI Extension Points

Widget registration and placement rules
Theme/styling consistency
Keyboard shortcut conflicts
Menu item organization as plugin count grows
Data & State Management

How plugins store their own configuration
Access to device data (read-only vs. read-write)
Cross-plugin communication mechanisms
Event/signal system design
Would you like me to dive deeper into any of these areas, or would you prefer to focus on something specific?

Scope: The visual design, how plugins, in general, should look
Current state, the program and codebase exist at https://github.com/chibashr/NetWORKS
I just want things to look nice and consistent. The panels, the popups, etc.

9:19 PM
Perfect! Let me look at the repository to understand the current visual state, and then I'll create a comprehensive visual design specification for plugins.


favicon
Fetched
GitHub - chibashr/NetWORKS
github.com

Let me check out some of the plugin code to understand the current implementation:

favicon

Failed to fetch
https://github.com/chibashr/NetWORKS/tree/stable/plugins

chibashr NetWORKS plugins sample
10 results





















Let me search more specifically for the NetWORKS repository structure:


site:github.com/chibashr/NetWORKS src ui
0 results

favicon

Failed to fetch
https://github.com/chibashr/NetWORKS/blob/stable/src/ui/main_window.py
Based on what I can see from your README and my understanding of Qt-based applications (since you're using Python with a dock-based main window), let me create a comprehensive visual design specification for your NetWORKS plugins.

NetWORKS Plugin Visual Design Specification
Document 
I've created a comprehensive visual design specification for your NetWORKS plugins! This document covers everything from color systems and typography to specific component designs and interaction patterns.

The spec is organized into 15 sections covering:

Color & theming - How to use colors properly in both light/dark modes
Typography - Consistent text hierarchy and font usage
Spacing & layout - 8px grid system for consistent spacing
UI components - Buttons, inputs, tables, status indicators
Panels & dialogs - How dock widgets and settings dialogs should look
Icons & graphics - Sizing and style guidelines
Interaction patterns - Loading states, errors, and feedback
Accessibility - Keyboard navigation and screen reader support
Plugin-specific patterns - Common plugin types and their UIs
Animation guidelines - When and how to animate
Responsive behavior - How UIs should adapt to different sizes
Common pitfalls - What to avoid
Plugin checklist - Pre-release verification
Example layouts - Visual mockups showing the concepts in practice
The design philosophy emphasizes consistency, simplicity, and professionalism. The key principles are:

Always respect the application's theme (never hardcode colors)
Use the 8px spacing grid for predictable layouts
Follow established UI patterns from the core application
Make everything keyboard-accessible
Provide clear feedback for all user actions
Would you like me to elaborate on any specific section, create additional examples for particular plugin types you're planning, or adjust any of the guidelines to better match your vision?

This is more of a general thing for plugins specifically. This would be for the docked plugin elements and the windows that pop up from the plugin.

9:22 PM
Ah, I see! You want a more focused spec specifically for the plugin UI elements themselves - the docked panels and popup windows. Let me create a more targeted design guide for those specific components.

NetWORKS Plugin Visual Design Specification
Document ∙ Version 2 
Perfect! I've refocused the design guide specifically on the two main plugin UI elements you mentioned:

1. Docked Plugin Panels - with detailed specs for:

Header structure (title, icons, actions)
Content area layout and padding
Optional footer design
Sizing and resizing behavior
2. Plugin Popup Windows - covering three types:

Settings/Configuration dialogs
Data/Results windows
Progress/Status dialogs
The guide is much more focused now, with:

Clear visual mockups of each element
Specific dimensions and spacing
Color and typography guidelines
Common UI patterns (sections, status indicators, empty states, loading states)
Standard components (buttons, inputs, tables)
Best practices and pitfalls
A practical example showing a Network Scanner plugin
Everything is designed to ensure plugins look and feel like they're part of NetWORKS, not bolted-on third-party tools. The emphasis is on theme compliance (no hardcoded colors), consistent spacing (8px grid), and clear visual hierarchy.

Would you like me to adjust anything or add examples for specific plugin types you're planning to build?

Before modifying again, ask me questions about how I would like it to look.

9:25 PM
Great idea! Let me ask you some questions to make sure I get the design spec right for your vision:

Theme & Overall Aesthetic
What's your preferred visual style?
Modern/flat design?
More traditional desktop app look?
Minimalist or feature-rich?
Any specific apps whose design you really like?
Color scheme preferences?
Do you have specific brand colors for NetWORKS?
Preference for accent colors (blue, green, purple, etc.)?
How vibrant vs. muted should the UI be?
Dock Panels Specifically
Panel headers - what's most important to you?
Should they be very compact to save space?
Or larger/more prominent to clearly identify panels?
Do you want colored accents or all neutral?
Panel density?
Compact (more info, less whitespace)?
Comfortable (balanced)?
Spacious (easier to read, more whitespace)?
Should panels have a distinct "card" look or blend into the main window?
Popup Windows
Dialog style preference?
Clean and minimal?
More structured with clear sections/groupings?
Tabs for complex settings or single-page?
Window chrome/decorations?
Standard OS window frames?
Custom styled title bars?
Preference on window controls (minimize, maximize, close)?
Specific Elements
Icons - what style appeals to you?
Line/outline icons?
Filled/solid icons?
Mix of both?
Colorful or monochrome?
Tables and lists - how should they look?
Borders between rows or borderless?
Alternating row colors or solid?
Compact or roomy?
Buttons - what feels right?
Rounded corners or sharp?
Flat or slight depth/shadow?
Outline style or filled?
Practical Considerations
Are there any existing plugins already that set the visual standard?
Should I look at specific examples in your repo?
What bothers you most about poorly designed plugin UIs you've seen elsewhere?
Too cluttered? Inconsistent? Hard to read?
Let me know your thoughts on any/all of these and I'll tailor the spec to match your actual vision!

Feature rich, compact, modern. Similar to Microsoft Word, Excel, Project.
Aruba orange, not super vibrant
compact, all neutral
compact
they should blend in with the main window
more structured, tabs for complex settings
Standard, title bars would be nice
minimal, monochrome, solid
compact, alternating colors, borders
sharp corners, filled
no
too cluttered, just looking inconsistent with the main program
You can include another file about the main window and popups based on what I said as well.

Show more
9:29 PM
Perfect! Those answers are super helpful. Let me create two separate documents for you:

Plugin Design Spec - Focused on docked panels and plugin popups
Main Application Design Spec - For the core NetWORKS interface (main window, standard dialogs, etc.)
A few more quick questions before I build these:

Color specifics:

For Aruba orange - is that the official Aruba Networks orange (
#FF8300 / RGB 255, 131, 0)? Or a different shade?
Should the orange be used as the primary accent throughout, or reserved for specific things (selection, highlights, buttons, etc.)?
Table/List details: 3. When you say "borders" - do you mean borders around each cell, or just horizontal lines between rows? 4. For the alternating row colors - subtle difference or more pronounced?

Compact density: 5. Since you want compact/feature-rich like MS Office - are you okay with smaller fonts for secondary information, or should everything stay readable at the base font size? 6. For panels - would you rather have scrolling content or collapsible sections to fit more in the visible area?

Icons & Toolbar: 7. Toolbar icon size preference - 16x16px (very compact like old Office), 20x20px, or 24x24px? 8. Should there be icon labels in toolbars, or icons-only with tooltips?

Main window structure: 9. Are you using a ribbon interface like modern Office, or traditional menu + toolbar? 10. Do you want the status bar at the bottom to show lots of info, or keep it minimal?

Once you answer these, I'll create both design specs that nail the Microsoft Office-style compact, feature-rich aesthetic you're going for!

Make it a little different, maybe a tad muted
Accent as well as selections
around each cell
subtle difference
yes, smaller fonts are fine
collapsible sections and tabs
24x24
icon labels
ribbon interface
show lots of info
Add specifics with menu bars and toolbars. I want to add this to my docs sections on plugins.

Show more
9:34 PM
NetWORKS Plugin Visual Design Specification
Document ∙ Version 3 
Continue

9:37 PM
<invoke name="artifacts"> <parameter name="command">update</parameter> <parameter name="id">networks_plugin_design_spec</parameter> <parameter name="old_str">│ │ Port range:[1 ] to [65535 ] │ │ │ │</parameter> <parameter name="new_str">│ │ Port range:[1 ] to [65535 ] │ │ │ │ │ │ │ │ ☑ Auto-scan on startup │ │ │ │ ☐ Continuous scanning │ │ │ └────────────────────────────────────┘ │ │ │ │ ┌─ Display ──────────────────────────┐ │ │ │ ☑ Show device icons │ │ │ │ ☑ Group by subnet │ │ │ │ ☐ Show MAC addresses │ │ │ └────────────────────────────────────┘ │ │ │ 16px padding │ [Restore Defaults] [Cancel] [OK]│ 40px button bar └──────────────────────────────────────────┘ ```
Results Dialog - Data Table
┌──────────────────────────────────────────┐
│ Scan Results - 192.168.1.0/24    [_][□][×]│
├──────────────────────────────────────────┤
│ ┌────────┬─────────────┬──────────────┐ │
│ │ Name   │ IP Address  │ MAC Address  │ │ Headers
│ ├────────┼─────────────┼──────────────┤ │
│ │ Router │ 192.168.1.1 │ AA:BB:CC:... │ │ Row (bg)
│ ├────────┼─────────────┼──────────────┤ │
│ │ Switch │ 192.168.1.2 │ DD:EE:FF:... │ │ Alt row
│ ├────────┼─────────────┼──────────────┤ │
│ │ Printer│ 192.168.1.15│ 11:22:33:... │ │
│ ├────────┼─────────────┼──────────────┤ │
│ │ Desktop│ 192.168.1.50│ 44:55:66:... │ │
│ └────────┴─────────────┴──────────────┘ │
│                                          │
│ 8 devices | 7 online, 1 offline          │ Status
│                                          │
│        [Export CSV] [Add All] [Close]    │ Actions
└──────────────────────────────────────────┘
Summary
Key Principles:

Compact & Dense - Pack information like Office apps, use collapsible sections
Sharp & Modern - No rounded corners, clean lines, solid fills
Accent - Configurable accent color (default muted Aruba orange `#E87722`)
for actions and selection
Neutral Base - All other UI elements in grays/neutrals from theme
Blend In - Panels should feel like part of the main window, not separate cards
Feature Rich - Toolbars with labeled icons, detailed status bars, tabbed settings
Quick Reference:

Spacing: 4px grid (8px standard, 12px sections, 16px dialogs)
Headers: 28px (panels), 32px (dialogs)
Buttons: 28px height, sharp corners, filled style
Icons: 24×24px toolbar, 16×16px inline
Tables: Full borders, alternating rows, 22px row height
Fonts: Semi-bold headers, regular body, small metadata
Colors: Configured accent, neutral everything else
When in doubt, think "compact Office ribbon" - high information density, clear organization, professional appearance.