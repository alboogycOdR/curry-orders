import 'package:flutter/material.dart';

/// Structured content for the Staff Help tab — a native, offline port of
/// `docs/STAFF_GUIDE.md` (the authoritative source; keep this in sync with
/// it). Split out from the screens themselves (`staff_help_screen.dart`,
/// `help_detail_screen.dart`) and their shared rendering widgets
/// (`help_widgets.dart`) so the actual guide text lives in one place as
/// plain data, not scattered across build methods.
///
/// `**bold**` inside a [HelpParagraph]/[HelpList] string renders as
/// emphasised text — see `help_widgets.dart`'s `buildRichText`.

/// One row of a reference table (see [HelpTable]).
class HelpTableRow {
  const HelpTableRow(this.cells);
  final List<String> cells;
}

abstract class HelpBlock {
  const HelpBlock();
}

/// A subsection heading inside a detail screen (e.g. "Actions", "The five
/// sections").
class HelpHeading extends HelpBlock {
  const HelpHeading(this.text);
  final String text;
}

/// Body copy.
class HelpParagraph extends HelpBlock {
  const HelpParagraph(this.text);
  final String text;
}

/// A bulleted (or numbered) list of short items.
class HelpList extends HelpBlock {
  const HelpList(this.items, {this.numbered = false});
  final List<String> items;
  final bool numbered;
}

enum HelpCalloutKind { info, warning, danger, success, rule }

/// A coloured callout box for a rule, warning or gate the guide calls out
/// specially — destructive actions, mandatory reasons, role restrictions.
class HelpCallout extends HelpBlock {
  const HelpCallout(this.kind, this.text, {this.title});
  final HelpCalloutKind kind;
  final String? title;
  final String text;
}

/// A simple reference table with a header row. The first cell of each row
/// renders bold (it's always the button/field/screen name).
class HelpTable extends HelpBlock {
  const HelpTable(this.headers, this.rows);
  final List<String> headers;
  final List<HelpTableRow> rows;
}

/// One step of a sequential order-lifecycle flow (see [HelpStepFlow]).
class HelpStep {
  const HelpStep({required this.icon, required this.title, required this.detail});
  final IconData icon;
  final String title;
  final String detail;
}

/// A vertical numbered stepper/timeline — used for the two "Complete order
/// flow" sections, which are literally sequential state machines in the
/// source guide.
class HelpStepFlow extends HelpBlock {
  const HelpStepFlow(this.steps, {this.terminalNote});
  final List<HelpStep> steps;
  final String? terminalNote;
}

/// One staff role's blurb, for the Roles section's role badges.
class HelpRoleInfo {
  const HelpRoleInfo({required this.icon, required this.role, required this.description});
  final IconData icon;
  final String role;
  final String description;
}

class HelpRoleList extends HelpBlock {
  const HelpRoleList(this.roles);
  final List<HelpRoleInfo> roles;
}

/// One question/answer pair for the Troubleshooting / FAQ section.
class HelpFaqEntry {
  const HelpFaqEntry(this.question, this.answer);
  final String question;
  final String answer;
}

class HelpFaqList extends HelpBlock {
  const HelpFaqList(this.entries);
  final List<HelpFaqEntry> entries;
}

/// One Help tab entry — a row on the landing screen, and the content of
/// its detail screen when tapped.
class HelpSection {
  const HelpSection({
    required this.id,
    required this.title,
    required this.teaser,
    required this.icon,
    required this.blocks,
  });

  final String id;
  final String title;
  final String teaser;
  final IconData icon;
  final List<HelpBlock> blocks;
}

// Ported from docs/STAFF_GUIDE.md (2026-09-14 revision), section by
// section, in the same order as the guide's own walkthrough.
const List<HelpSection> helpSections = [
  HelpSection(
    id: 'getting-in',
    title: 'Getting in',
    teaser: 'Logging in, Google sign-in, email links, lockouts, temporary passwords.',
    icon: Icons.login_rounded,
    blocks: [
      HelpParagraph(
        'The login page asks for your **Email** and **Password** — not a username.',
      ),
      HelpList([
        'Go to the login page.',
        'Type your email address and password.',
        'Click **Log in**.',
      ], numbered: true),
      HelpParagraph(
        'You land on the Inbox afterwards (or wherever you were trying to go, if a link '
        'sent you to login first).',
      ),
      HelpHeading('Other ways to sign in'),
      HelpList([
        '**Sign in with Google** — only works if your Google account\'s email has been '
            'added to the staff allow-list by an admin. If it hasn\'t, you\'ll see "Your '
            'Google account is not authorised as staff. Contact the owner."',
        '**Sign in by email link instead** — enter your staff email and, if it\'s on the '
            'allow-list, you\'ll be sent a one-time sign-in link (no password needed). For '
            'security the page always says a link was sent, even if your email isn\'t '
            'recognised.',
      ]),
      HelpCallout(
        HelpCalloutKind.warning,
        title: 'Locked out',
        'After too many wrong password attempts, the account locks for **15 minutes**. '
            'Contact the owner if you need in sooner.',
      ),
      HelpCallout(
        HelpCalloutKind.info,
        title: 'Temporary passwords',
        'If the owner has just set you up (or reset your password), you\'ll be forced '
            'straight to a "Set a new password" screen the first time you log in — you '
            'can\'t skip this. New passwords must be at least **10 characters**.',
      ),
      HelpParagraph(
        'Getting back here from the public website: on a phone, tap **More** in the '
        'bottom nav, then **Kitchen staff login**. On a wider screen while logged out, '
        'there\'s a small **Staff login** link in the site footer.',
      ),
      HelpParagraph(
        'Once logged in, look for the **Staff** dropdown in the top-right of every page — '
        'it\'s your menu for every staff screen: Inbox, Calendar, Kitchen desk, '
        'Collection, Payments, Cash, Daily controls, Menu editor, New assisted order, and '
        '(owners only) Settings, plus **Log out** at the bottom.',
      ),
    ],
  ),
  HelpSection(
    id: 'inbox',
    title: 'Inbox',
    teaser: 'Your morning briefing — five sections, shown only when there\'s something to do.',
    icon: Icons.inbox_rounded,
    blocks: [
      HelpParagraph(
        'The landing page after login. It pulls together everything across the whole '
        'system that might need attention *right now*, in five sections, each shown only '
        'if it has something in it. If every section is empty you\'ll see a plain "Inbox '
        'is clear — nothing needs attention right now."',
      ),
      HelpHeading('The five sections'),
      HelpTable(
        ['Section', 'What\'s in it'],
        [
          HelpTableRow([
            'Cash requests',
            'Every order a customer placed choosing to pay cash on collection, still '
                'waiting for accept/reject. Same list as the dedicated Cash screen.',
          ]),
          HelpTableRow([
            'Hold lapsed / SLA breached',
            'EFT orders whose payment hold has already run out with no proof uploaded, '
                'and orders sitting in "payment review" longer than the settings-configured '
                'review window (15 minutes by default). Both need a decision on Payments.',
          ]),
          HelpTableRow([
            'Orders with notes',
            'Any still-open order carrying a customer note — most recent 30. Check for '
                'dietary requirements or special requests before they reach the kitchen.',
          ]),
          HelpTableRow([
            'Recent assisted',
            'The last 20 orders staff created on the customer\'s behalf (phone, WhatsApp, '
                'in-person) — shown for reference/follow-up, not for action.',
          ]),
          HelpTableRow([
            'Recently expired',
            'Orders whose EFT hold expired in the last 48 hours, with a Reinstate option '
                'in case the customer still wants to pay.',
          ]),
        ],
      ),
      HelpHeading('What each row shows'),
      HelpParagraph(
        'Every row shows the order number (opens the customer\'s own order-status page in '
        'a new tab), the customer\'s name with a **WhatsApp** link when a mobile number is '
        'on file, the collection day/slot, the status (plus note text, if any), who it\'s '
        'assigned to, and a row of action buttons.',
      ),
      HelpList([
        '**Assign to me / Unassign** — every row. Puts your name against the order, or '
            'takes it back off. Just a label, not a status change.',
        '**Accept / Reject** — cash-request rows only. Accept moves the order to '
            '`cash_due` (appears on Kitchen desk); Reject cancels it and frees the slot.',
        '**Reinstate** — recently-expired rows only. Asks for a reason, then puts the '
            'order back into Awaiting EFT with a brand new payment hold — only works if '
            'the day/slot/dishes still have room.',
        '**Move to… / Move** — a dropdown of that day\'s other open slots plus a Move '
            'button. Changes the collection slot only, nothing else about the order.',
      ]),
      HelpCallout(
        HelpCalloutKind.warning,
        'If any button fails (someone else already actioned the order, for example), '
        'the row shows "Action failed — reload the page to check this order\'s current '
        'status" rather than silently doing nothing.',
      ),
    ],
  ),
  HelpSection(
    id: 'calendar',
    title: 'Calendar',
    teaser: 'An 8-day grid — spot a full day or a dish about to sell out.',
    icon: Icons.calendar_month_rounded,
    blocks: [
      HelpParagraph(
        'An 8-day grid (today plus the next 7 days) showing how full each day is at a '
        'glance. Each day is a clickable card that takes you straight to that day\'s '
        '**Daily controls** screen to make changes.',
      ),
      HelpHeading('Each card shows'),
      HelpList([
        'The date, and an **Open / Closed** badge for whether the day is taking orders '
            'at all.',
        '**Orders: X / Y** — how many orders are booked against that day\'s order cap.',
        '**Cash: X / Y** — how many of those are cash orders, against the cash cap.',
        'A row of small coloured bars, one per collection slot, showing how full each '
            'slot is (hover for exact time and occupancy). Grey = empty, light green = '
            'under 50% full, yellow = 50–89% full, orange = 90%+ full.',
        'A warning line for any dish at 80% or more of its daily unit cap for that day '
            '(e.g. "Chicken Masala Roti Roll: 16/20 — cap or mark unavailable").',
      ]),
      HelpCallout(
        HelpCalloutKind.info,
        'Use this screen to spot a day filling up, or a dish about to run out, before it '
        'becomes a problem — then click through to Daily controls to act on it.',
      ),
    ],
  ),
  HelpSection(
    id: 'kitchen-desk',
    title: 'Kitchen desk',
    teaser: 'Today\'s cook list, prep lock, and Start kitchen / Mark ready.',
    icon: Icons.soup_kitchen_rounded,
    blocks: [
      HelpParagraph(
        'Shows today\'s board by default; use **← Prev day / Next day →** to look at '
        'another day, or **Print** for a clean prep sheet (buttons/nav are hidden when '
        'printing).',
      ),
      HelpParagraph(
        'Orders land here the moment they\'re confirmed — either an EFT payment is '
        'verified, or a cash order is accepted — and leave once marked ready (to the '
        'Collection board).',
      ),
      HelpHeading('What you see'),
      HelpList([
        '**Two meters** at the top: orders secured today (against the order cap) and '
            'cash orders today (against the cash cap).',
        '**Summary** — every dish/option combination across today\'s orders, with total '
            'quantity needed and which order numbers contribute to it. Your cook list.',
        '**Lock prep list** — stamps the current time as the kitchen\'s "prep locked" '
            'time. After locking, anything confirmed later shows up separately in '
            '**Added after lock**.',
        '**Exceptions** — any order with a customer note, a kitchen note, or an allergen '
            'flag, listed with the actual text.',
        '**Added after lock** — only appears once locked; lists orders confirmed after '
            'that point.',
        '**Today\'s run** — one row per order: slot time, order number, customer, item '
            'summary, EFT/CASH tag, status, and an action button.',
      ]),
      HelpCallout(
        HelpCalloutKind.danger,
        '**Lock prep list** cannot be undone once clicked — there\'s no unlock.',
      ),
      HelpHeading('Actions'),
      HelpTable(
        ['Button', 'Appears when', 'What it does', 'Order moves to'],
        [
          HelpTableRow([
            'Start kitchen',
            'Confirmed (prep) or Cash due',
            'Marks cooking as started',
            'In kitchen — customer sees "Cooking"',
          ]),
          HelpTableRow([
            'Mark ready',
            'In kitchen',
            'Food is packaged and ready',
            'Ready — customer sees "Ready to collect", appears on Collection board',
          ]),
        ],
      ),
      HelpParagraph(
        'Two bulk buttons above the run list — **Start kitchen (all confirmed)** and '
        '**Mark ready (all in kitchen)** — each with a confirmation pop-up, for when a '
        'whole batch moves together.',
      ),
      HelpCallout(
        HelpCalloutKind.warning,
        'This page doesn\'t auto-refresh — reload to see other staff members\' changes. '
        'A failed click shows a "reload the page" error rather than failing silently.',
      ),
    ],
  ),
  HelpSection(
    id: 'collection',
    title: 'Collection board',
    teaser: 'Ready orders by slot, ticket tags, Collected, and the Uncollected bucket.',
    icon: Icons.storefront_rounded,
    blocks: [
      HelpParagraph(
        'Shows all orders that are ready (or about to be), grouped by collection time '
        'slot in time order; the current slot is highlighted with a **Now** tag. Use '
        '**← Prev day / Next day →** for other days.',
      ),
      HelpHeading('Ticket appearance'),
      HelpParagraph(
        'Each order is a card: order number, customer name, item count, and a tag — '
        '**CASH R##.##** (amount to collect) or **PAID** (EFT, already settled). A card '
        'still **In kitchen** (not ready yet) is shown faded/greyed with a "Not ready" '
        'tag.',
      ),
      HelpHeading('Actions per ticket'),
      HelpTable(
        ['Button', 'Appears when', 'What it does', 'Order moves to'],
        [
          HelpTableRow([
            'Mark ready',
            'In kitchen',
            'Fast-track straight from here, if not already marked on Kitchen desk',
            'Ready',
          ]),
          HelpTableRow([
            'Collected',
            'Ready',
            'Customer has arrived and picked up their food',
            'Collected (done)',
          ]),
          HelpTableRow([
            'Uncollect',
            'Collected',
            'Undo an accidental Collected tap — asks for a reason first',
            'Back to Ready',
          ]),
        ],
      ),
      HelpCallout(
        HelpCalloutKind.danger,
        '**Uncollect only works within 10 minutes** of the original Collected click. '
        'After that the button stops working — tell the developer/owner if a genuine '
        'mistake needs correcting past that window.',
      ),
      HelpHeading('Uncollected bucket'),
      HelpParagraph(
        'Once the collection window plus a grace period (15 minutes by default) has '
        'passed, any order still Ready moves out of its slot group into a separate '
        '**Uncollected** section at the bottom, each with a **No-show** button '
        '(confirmation: "This cannot be undone"). No-show cancels the order; the '
        'food/units stay counted as used.',
      ),
      HelpHeading('Close out day'),
      HelpCallout(
        HelpCalloutKind.danger,
        'Once the same deadline has passed, a **Close out day** box appears. It tells '
        'you how many remaining ready orders will be marked as no-shows, and asks you to '
        'confirm the exact count before proceeding. This is the same action a nightly '
        'automatic job runs at 23:30 SAST anyway (a safety net) — the button here just '
        'does it early and on demand. It cannot be undone.',
      ),
    ],
  ),
  HelpSection(
    id: 'payments',
    title: 'Payments — EFT queue',
    teaser: 'Verify, reject, expire, or extend a bank-transfer payment hold.',
    icon: Icons.account_balance_rounded,
    blocks: [
      HelpParagraph(
        'Shows every order waiting on an EFT (bank transfer) payment, oldest-lapsing-hold '
        'first, then by slot time. Cash orders never appear here — those are on the Cash '
        'screen.',
      ),
      HelpTable(
        ['Status shown', 'Meaning'],
        [
          HelpTableRow([
            'Awaiting EFT',
            'Order placed, payment hold timer running, customer hasn\'t uploaded proof yet',
          ]),
          HelpTableRow([
            'Payment review',
            'Customer has uploaded proof of payment — needs a staff member to check it',
          ]),
        ],
      ),
      HelpParagraph(
        'Each row also shows the amount, the collection slot, a live-updating hold '
        'countdown (or "Lapsed — hold expired" in red once it runs out), and whether '
        'proof has been uploaded (**Uploaded** or **—**).',
      ),
      HelpHeading('Actions per order'),
      HelpTable(
        ['Button', 'Shown when', 'What it does', 'Order moves to'],
        [
          HelpTableRow([
            'Verify',
            'Payment review',
            'Proof looks correct — accept the payment',
            'Confirmed (prep) → Kitchen desk',
          ]),
          HelpTableRow([
            'Verify (seen in bank app)',
            'Awaiting EFT',
            'You can see the payment landed even without a proof screenshot — asks for a '
                'reason first',
            'Confirmed (prep)',
          ]),
          HelpTableRow([
            'Reject',
            'Payment review',
            'Proof is wrong/invalid — asks for a reason first',
            'Back to Awaiting EFT (hold isn\'t extended automatically — use Extend hold too)',
          ]),
          HelpTableRow([
            'Expire now',
            'Awaiting EFT',
            'Manually close the hold early',
            'Payment expired (dead end — reinstatable from Inbox within 48 hours)',
          ]),
          HelpTableRow([
            'Extend hold',
            'Always',
            'Adds the current EFT hold window to the deadline',
            'Stays in Awaiting EFT, deadline pushed out',
          ]),
        ],
      ),
      HelpCallout(
        HelpCalloutKind.info,
        'Clicking **Verify** updates the customer\'s own tracker on their phone from '
        '"Payment" straight to "Confirmed" immediately.',
      ),
      HelpCallout(
        HelpCalloutKind.warning,
        'Hold extensions are limited — by default an order\'s hold can only be extended '
        '**once**. Extending again past that limit fails with a message saying the '
        'maximum extensions have been used.',
      ),
      HelpParagraph('This page doesn\'t auto-refresh either — reload to see other staff members\' changes.'),
    ],
  ),
  HelpSection(
    id: 'cash',
    title: 'Cash requests',
    teaser: 'Accept or reject cash-on-collection orders.',
    icon: Icons.payments_rounded,
    blocks: [
      HelpParagraph(
        'Every order where the customer chose to pay cash on collection, oldest first — '
        'a same-day queue, no date picker. The exact same list as the Inbox\'s "Cash '
        'requests" section, just without everything else around it.',
      ),
      HelpTable(
        ['Button', 'What it does', 'Order moves to'],
        [
          HelpTableRow([
            'Accept',
            'Confirms the order — moves it to the kitchen board as cash-due',
            'Cash due → Kitchen desk (still needs cash collected on pickup)',
          ]),
          HelpTableRow([
            'Reject',
            'Declines the request — cancels the order and frees its slot capacity. '
                'Confirmation: "Reject this cash order? It will be cancelled and the slot freed."',
            'Cancelled',
          ]),
        ],
      ),
    ],
  ),
  HelpSection(
    id: 'daily-controls',
    title: 'Daily controls',
    teaser: 'Override one day — sell out a dish, close a slot, close the whole day.',
    icon: Icons.tune_rounded,
    blocks: [
      HelpParagraph(
        'Visiting with no date takes you straight to today\'s page. This screen is your '
        'day-by-day override layer — sell out one dish, close one slot, or close the '
        'whole day, without touching the monthly menu (that\'s the Menu editor).',
      ),
      HelpHeading('Day section'),
      HelpList([
        '**Open** checkbox — whether the day is taking orders at all.',
        '**Daily order cap** — override just for this day.',
        '**Same-day cut-off** — the time same-day ordering closes.',
        '**Window start / Window end** — the collection window for the day.',
        '**Internal notes** — free-text, staff-only, not shown to customers.',
      ]),
      HelpHeading('Slots table'),
      HelpParagraph(
        'One row per collection slot: its time window, an editable capacity number (it '
        'can never be set below the slot\'s current occupancy — you\'ll get a validation '
        'error listing the minimum), a **Closed** checkbox, and a read-only "Occupying" '
        'count.',
      ),
      HelpHeading('Dishes today table'),
      HelpParagraph(
        'One row per active dish: an **Available** checkbox for that specific day, a '
        '**Max units** number (leave blank for uncapped), and a read-only "Used today" '
        'count.',
      ),
      HelpHeading('Saving'),
      HelpParagraph('Click **Save daily controls** at the bottom.'),
      HelpCallout(
        HelpCalloutKind.warning,
        title: 'Closing something that already has orders on it',
        'If your changes would affect orders that already exist — closing a slot or the '
        'whole day while it still has active orders — the page won\'t save immediately. '
        'You\'ll see a warning box listing every affected order (number, customer, '
        'status), plus a **Move all to…** dropdown + Move all button per affected slot, '
        'and a checkbox: "I understand this affects the orders listed above and want to '
        'save anyway." Tick it (after moving orders, or deliberately leaving them) and '
        'click Save again to go through.',
      ),
      HelpCallout(
        HelpCalloutKind.success,
        'Existing orders on a slot or day you close **keep their booking** — closing '
        'only stops *new* orders being placed against it.',
      ),
    ],
  ),
  HelpSection(
    id: 'menu-editor',
    title: 'Menu editor',
    teaser: 'Dishes, options & values, image upload, archive / unarchive.',
    icon: Icons.restaurant_menu_rounded,
    blocks: [
      HelpParagraph(
        'Lists every dish, including archived ones, in the same order they appear on the '
        'public menu (category, then sort order, then name) — archived dishes are shown '
        'dimmed at the end of their category. Each row shows category, sort order, name '
        '(a link to edit), price, whether it\'s active on the public menu, a Live/Archived '
        'badge, and how many currently-active orders reference that dish.',
      ),
      HelpList([
        '**+ New dish** (top right) opens a blank dish form.',
        'Click a dish\'s name, or **Edit**, to open its edit form.',
      ]),
      HelpHeading('The dish form'),
      HelpParagraph(
        'Fields: Slug (create only — permanent once set, cannot be changed afterwards), '
        'Name, Price (cents), Portion label, Short description, Long description, Spice '
        'default, Allergen text, Dietary tags, Category, Sort order, "Is active on menu" '
        'checkbox, "Allow notes" checkbox. Click **Create dish** or **Save dish**.',
      ),
      HelpHeading('Image upload (edit screen only)'),
      HelpParagraph(
        'A separate small form below the main one: choose a JPEG/PNG/WebP file and click '
        '**Upload image**.',
      ),
      HelpHeading('Options & values (edit screen only)'),
      HelpParagraph('For things like spice level, size, or extras:'),
      HelpList([
        'Add an option with a name, a **Required** checkbox, and a sort number, via the '
            '**Add option** form at the bottom.',
        'Under each option, add values (name, price delta in cents, sort order) via its '
            'own **Add value** form; each value has a Yes/No availability toggle and a '
            '**Delete** button (confirmation — deleting is permanent).',
        '**Delete option** removes the option and all its values — also asks for '
            'confirmation first.',
      ]),
      HelpHeading('Archiving a dish'),
      HelpCallout(
        HelpCalloutKind.warning,
        title: 'Archive dish',
        'A boxed section at the bottom. If the dish has no orders currently using it, '
        'one click archives it (confirmed via pop-up) and it disappears from the public '
        'menu immediately. If it does have active orders referencing it, you\'ll see the '
        'exact count and must tick a confirmation checkbox before the button will go '
        'through — safe to do even then, because every existing order line keeps its own '
        'frozen copy of the dish\'s name and price regardless of what happens to the Dish '
        'record afterwards.',
      ),
      HelpCallout(
        HelpCalloutKind.success,
        'Archiving is a **soft delete** — an **Unarchive** button on the dish\'s edit '
        'page brings it back.',
      ),
    ],
  ),
  HelpSection(
    id: 'new-assisted-order',
    title: 'New assisted order',
    teaser: 'Place an order on a customer\'s behalf — phone, walk-in, or WhatsApp.',
    icon: Icons.phone_forwarded_rounded,
    blocks: [
      HelpParagraph(
        'For staff placing an order on the customer\'s behalf — a phone-in order, a '
        'walk-in customer, or someone ordering via a WhatsApp conversation with you. '
        'Never used for the customer\'s own self-service web checkout (those always come '
        'through as "Website" orders automatically).',
      ),
      HelpCallout(
        HelpCalloutKind.info,
        'It uses exactly the same underlying reservation logic as the customer\'s own '
        'online checkout — same capacity checks, same dish-availability rules, same '
        'order numbering — so anything placed here counts against the day/slot/cash/dish '
        'caps exactly like a normal web order would.',
      ),
      HelpHeading('Before you start, get from the customer'),
      HelpList([
        'Their full name.',
        'Their mobile number (must be a valid South African mobile number).',
        'What they want to order (dish, quantity, and any required options like spice '
            'level or size).',
        'Which collection slot they want.',
        'How they\'re paying — EFT or cash (cash only shows if currently enabled in '
            'Settings).',
        'If it\'s a same-day order placed after the normal cut-off, a short reason — and '
            'this only works if the owner has turned that feature on.',
      ]),
      HelpHeading('Customer section'),
      HelpList([
        '**Full name** — free text, 2–80 characters.',
        '**Mobile number** — must resolve to a valid SA mobile number.',
        '**Order source** — radio buttons: Phone, In person, or WhatsApp (assisted).',
        '**Order note** (optional) — up to 200 characters, visible to the kitchen.',
      ]),
      HelpHeading('Collection section'),
      HelpList([
        '**Slot** — a dropdown of the day\'s slots with current occupancy (e.g. '
            '"12:00–12:30 (4/10)"); full/closed slots are disabled.',
        '**After-cut-off reason** — only shown for today\'s date. If enabled in Settings, '
            'this becomes a required field for a same-day order placed after cut-off. If '
            'the setting is off, the field is shown disabled with an explanatory note.',
      ]),
      HelpHeading('Payment section'),
      HelpTable(
        ['EFT status option', 'Use when', 'Effect'],
        [
          HelpTableRow([
            'Awaiting EFT (default)',
            'The normal case',
            'Created exactly like a web order, with a payment hold running; shows on the '
                'Payments queue once the customer pays',
          ]),
          HelpTableRow([
            'Customer says paid',
            'Customer tells you (e.g. over the phone) they\'ve already paid, no proof yet',
            'Moves straight into Payment review — the same queue a real proof upload '
                'would land it in',
          ]),
          HelpTableRow([
            'Staff saw the funds',
            'You have personally already seen the money land in the bank account',
            'Confirms the payment immediately (no waiting), sends the order straight to '
                'the kitchen board',
          ]),
        ],
      ),
      HelpCallout(
        HelpCalloutKind.danger,
        'A **reason is mandatory** for "Staff saw the funds" — a text box appears; you '
        'must fill it in or the order can\'t be escalated this way (it can still be '
        'created as a plain hold instead).',
      ),
      HelpHeading('Dishes section'),
      HelpParagraph(
        'Every active dish for the selected day, each with a quantity box (0–20) and, '
        'where the dish has options, the choices inline underneath — required options '
        'are radio buttons (pick one), optional ones are checkboxes (pick any). A dish '
        'sold out for the day is greyed out with "— sold out today" and its quantity box '
        'disabled.',
      ),
      HelpParagraph(
        'Click **Create order** at the bottom. On success you\'re taken back to the '
        'Inbox with a confirmation message naming the new order number.',
      ),
      HelpCallout(
        HelpCalloutKind.info,
        'If the escalation to "Payment review" or "Staff saw the funds" fails for some '
        'reason (e.g. the reason was somehow missing), the order is still created as a '
        'plain hold — you\'ll get a warning message rather than losing the order '
        'entirely.',
      ),
      HelpCallout(
        HelpCalloutKind.warning,
        'If something\'s wrong with the form — a missing name, an invalid mobile number, '
        'no dishes selected, no slot chosen, capacity ran out since you loaded the page — '
        'you\'ll see specific error messages at the top and nothing is created. Fix the '
        'fields called out and click Create order again.',
      ),
    ],
  ),
  HelpSection(
    id: 'other-screens',
    title: 'Other screens',
    teaser: 'Settings, Team, and Change password.',
    icon: Icons.apps_rounded,
    blocks: [
      HelpTable(
        ['Screen', 'Who can use it', 'What it\'s for'],
        [
          HelpTableRow([
            'Settings',
            'Owner and Admin only',
            'Order/cash caps, EFT hold duration, extension limits, collection grace '
                'period, bank details, and around 40 other site-wide settings — every '
                'field maps directly to a setting. Every save is written to a settings '
                'audit log automatically. Shown in the Staff dropdown for Owner and Admin.',
          ]),
          HelpTableRow([
            'Team',
            'Admin only (not Owner)',
            'Invite staff by email (choose their role: admin/owner/manager), remove '
                'someone from the allow-list, or change someone\'s role. Shown in the '
                'Staff dropdown for Admins. An Owner needing this must ask an Admin — '
                'Owner is redirected away with "Team management requires admin access."',
          ]),
          HelpTableRow([
            'Change password',
            'Any logged-in staff',
            'Voluntary password change, or the forced screen you land on with a '
                'temporary password.',
          ]),
        ],
      ),
    ],
  ),
  HelpSection(
    id: 'roles',
    title: 'Roles',
    teaser: 'Manager, Owner, Admin — who can do what.',
    icon: Icons.badge_rounded,
    blocks: [
      HelpParagraph(
        'There are three staff roles (`UserRole` in the system): **Admin**, **Owner**, '
        'and **Manager**.',
      ),
      HelpRoleList([
        HelpRoleInfo(
          icon: Icons.groups_rounded,
          role: 'Manager',
          description: 'Everyday access to every board: Inbox, Calendar, Kitchen desk, '
              'Collection, Payments, Cash, Daily controls, Menu editor, New assisted '
              'order.',
        ),
        HelpRoleInfo(
          icon: Icons.workspace_premium_rounded,
          role: 'Owner',
          description: 'Everything a Manager can do, plus Settings, plus one extra '
              'permission: only an Owner or Admin can cancel an order once it\'s already '
              'In kitchen or Ready. A Manager trying this gets an "Only the owner can '
              'cancel from this stage" error.',
        ),
        HelpRoleInfo(
          icon: Icons.admin_panel_settings_rounded,
          role: 'Admin',
          description: 'Everything an Owner can do, plus Team management — invite/remove '
              'staff and change roles.',
        ),
      ]),
      HelpCallout(
        HelpCalloutKind.rule,
        'If you try an action your role doesn\'t allow, you won\'t be shown a broken '
        'page — the system either hides the button/link entirely, or (for '
        'Settings/Team specifically) shows a plain "access only"/"requires admin '
        'access" message and sends you back to the Inbox.',
      ),
    ],
  ),
  HelpSection(
    id: 'order-flow-eft',
    title: 'Complete order flow — EFT',
    teaser: 'The full bank-transfer order lifecycle, step by step.',
    icon: Icons.timeline_rounded,
    blocks: [
      HelpStepFlow(
        [
          HelpStep(
            icon: Icons.shopping_cart_checkout_rounded,
            title: 'Order placed',
            detail: 'Customer places order (or staff places an assisted order).',
          ),
          HelpStep(
            icon: Icons.hourglass_top_rounded,
            title: 'Awaiting EFT',
            detail: 'Payments screen — hold timer running. Customer uploads proof, or '
                'staff marks "Customer says paid".',
          ),
          HelpStep(
            icon: Icons.fact_check_rounded,
            title: 'Payment review',
            detail: 'Payments screen — staff clicks VERIFY.',
          ),
          HelpStep(
            icon: Icons.receipt_long_rounded,
            title: 'Confirmed (prep)',
            detail: 'Kitchen desk — staff clicks START KITCHEN.',
          ),
          HelpStep(
            icon: Icons.soup_kitchen_rounded,
            title: 'In kitchen',
            detail: 'Kitchen desk / Collection board — staff clicks MARK READY.',
          ),
          HelpStep(
            icon: Icons.storefront_rounded,
            title: 'Ready',
            detail: 'Collection board — customer arrives, staff clicks COLLECTED.',
          ),
          HelpStep(
            icon: Icons.check_circle_rounded,
            title: 'Collected',
            detail: 'Done.',
          ),
        ],
        terminalNote: 'A hold that runs out with no action becomes **Payment expired** — '
            'a dead end unless reinstated from the Inbox within 48 hours (a fresh hold is '
            'created).',
      ),
    ],
  ),
  HelpSection(
    id: 'order-flow-cash',
    title: 'Complete order flow — cash',
    teaser: 'The full cash-on-collection order lifecycle, step by step.',
    icon: Icons.alt_route_rounded,
    blocks: [
      HelpStepFlow(
        [
          HelpStep(
            icon: Icons.shopping_cart_checkout_rounded,
            title: 'Cash order placed',
            detail: 'Customer places a cash order (or staff places an assisted cash '
                'order).',
          ),
          HelpStep(
            icon: Icons.payments_rounded,
            title: 'Cash request',
            detail: 'Cash screen — staff clicks ACCEPT.',
          ),
          HelpStep(
            icon: Icons.receipt_long_rounded,
            title: 'Cash due',
            detail: 'Kitchen desk — staff clicks START KITCHEN.',
          ),
          HelpStep(
            icon: Icons.soup_kitchen_rounded,
            title: 'In kitchen',
            detail: 'Kitchen desk / Collection board — staff clicks MARK READY.',
          ),
          HelpStep(
            icon: Icons.storefront_rounded,
            title: 'Ready',
            detail: 'Collection board — customer pays cash + staff clicks COLLECTED.',
          ),
          HelpStep(
            icon: Icons.check_circle_rounded,
            title: 'Collected',
            detail: 'Done.',
          ),
        ],
        terminalNote: 'Rejecting a cash request, or an order left Ready past the '
            'collection deadline with no-show/close-out applied, both end in '
            '**Cancelled**.',
      ),
    ],
  ),
  HelpSection(
    id: 'quick-reference',
    title: 'Quick reference',
    teaser: 'What the customer sees on their tracker at each step.',
    icon: Icons.visibility_rounded,
    blocks: [
      HelpTable(
        ['Order status (internal)', 'Customer tracker shows'],
        [
          HelpTableRow(['Awaiting EFT', '"Payment" step — upload your proof of payment']),
          HelpTableRow(['Payment review', '"Payment" step — proof is with us, confirming shortly']),
          HelpTableRow(['Cash request', 'Waiting for staff to accept the cash order']),
          HelpTableRow(['Confirmed (prep) / Cash due', '"Confirmed" step']),
          HelpTableRow(['In kitchen', '"Cooking" step']),
          HelpTableRow(['Ready', '"Ready to collect" step']),
          HelpTableRow(['Collected', 'Terminal — order complete']),
          HelpTableRow(['Payment expired / Cancelled', 'Terminal — order ended']),
        ],
      ),
    ],
  ),
  HelpSection(
    id: 'troubleshooting',
    title: 'Troubleshooting / FAQ',
    teaser: 'Common questions — buttons that fail, reason boxes, role errors.',
    icon: Icons.live_help_rounded,
    blocks: [
      HelpFaqList([
        HelpFaqEntry(
          'A button did nothing, or a row shows a red error saying to reload the page.',
          'Someone else (or a background job) already changed that order\'s status since '
          'your screen loaded — the system refuses to apply an action against a status it '
          'no longer matches, to stop two staff members\' clicks from clashing. Reload '
          'the page and check the order\'s current status before trying again.',
        ),
        HelpFaqEntry(
          'I tried to cancel an order that\'s already In kitchen or Ready and got an '
          'error.',
          'That\'s expected if you\'re a Manager — only an Owner or Admin can cancel an '
          'order at that late a stage. Ask an Owner/Admin to do it, or hold the order at '
          'that status and contact the customer directly.',
        ),
        HelpFaqEntry(
          'A "reason" box suddenly appeared and won\'t let me submit without text.',
          'A handful of actions are deliberately gated behind a mandatory reason, because '
          'they bypass a normal safety check: verifying EFT payment without proof ("seen '
          'in bank app"), rejecting a payment, reinstating an expired order, uncollecting '
          'an order, and confirming "Staff saw the funds" on an assisted order. Type a '
          'short, honest reason (e.g. "Customer showed me the bank SMS") — it\'s recorded '
          'against the order for the audit trail, it isn\'t shown to the customer.',
        ),
        HelpFaqEntry(
          'I marked an order Collected by mistake.',
          'Use Uncollect on the Collection board — but only within 10 minutes of the '
          'original click. After that the button stops working; ask the developer/owner '
          'if a correction is genuinely needed past that window.',
        ),
        HelpFaqEntry(
          'An EFT hold ran out before the customer paid.',
          'The order moves to Payment expired automatically and drops off the Payments '
          'queue. It still shows up in the Inbox\'s "Recently expired" section for 48 '
          'hours, where you can Reinstate it (with a reason) — that opens a brand-new '
          'hold, but only if the day/slot/dish still has room. After 48 hours it\'s '
          'easiest to just have the customer place a new order.',
        ),
        HelpFaqEntry(
          'I can\'t extend a hold any further.',
          'Holds can only be extended a limited number of times (one, by default) — '
          'Extend hold will refuse once that limit is hit. Use Verify (seen in bank app) '
          'if you can confirm the payment another way, or let it lapse and reinstate '
          'later if the customer still wants to order.',
        ),
        HelpFaqEntry(
          'A slot or dish won\'t let me set its capacity/limit below a certain number.',
          'Daily controls won\'t let a slot\'s capacity go below how many orders are '
          'already occupying it — you\'ll see the exact minimum in a validation message. '
          'Move some of those orders to another slot first (the "Move all to…" tool in '
          'the confirmation banner) if you need to shrink it further.',
        ),
        HelpFaqEntry(
          'I\'m a Manager and can\'t see a Settings link.',
          'Correct — Settings is Owner/Admin only, and the link is hidden from Managers '
          'entirely (not just blocked). Owner and Admin both see it in the Staff '
          'dropdown.',
        ),
        HelpFaqEntry(
          'I need to add or remove a staff member, or change someone\'s role.',
          'That\'s the Team screen — Admin role only (an Owner cannot do this, even '
          'though Owner outranks Manager everywhere else). Admins see a link to it in '
          'the Staff dropdown.',
        ),
        HelpFaqEntry(
          'A dish I need to sell out today isn\'t in Daily controls.',
          'Daily controls only lists dishes that are active on the public menu ("Is '
          'active on menu" checked in the Menu editor). Check the Menu editor first if a '
          'dish seems to be missing.',
        ),
      ]),
    ],
  ),
];
