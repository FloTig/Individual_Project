// Chores widget for Scriptable (free on the App Store).
//
// Don't copy this file by hand: in the Chores app, tap your name, then "Copy widget script".
// That copy has the app's address and your personal key filled in. In Scriptable, tap +,
// paste it and name it Chores. Then add a Scriptable widget to your Home Screen (small,
// medium or large) or Lock Screen, edit the widget and pick the Chores script.
// Tapping the widget opens Chores in Safari.

const BASE = "__ORIGIN__";
const KEY = "__KEY__";

const family = config.widgetFamily || "medium";
const ink = Color.dynamic(new Color("#1d2430"), new Color("#eef2f5"));
const ink2 = Color.dynamic(new Color("#1d2430", 0.6), new Color("#eef2f5", 0.62));
const rose = Color.dynamic(new Color("#c2415a"), new Color("#ff8da1"));

// The same pastel mist as the app.
function mist() {
  const g = new LinearGradient();
  g.colors = [
    Color.dynamic(new Color("#dcebe3"), new Color("#15302b")),
    Color.dynamic(new Color("#e8e4f6"), new Color("#221d36")),
    Color.dynamic(new Color("#f6e3d9"), new Color("#2b1f1d")),
  ];
  g.locations = [0, 0.55, 1];
  g.startPoint = new Point(0, 0);
  g.endPoint = new Point(1, 1);
  return g;
}

function text(stack, value, font, color, lines) {
  const t = stack.addText(value);
  t.font = font;
  t.textColor = color;
  if (lines) t.lineLimit = lines;
  return t;
}

async function image(path) {
  try {
    return await new Request(BASE + path).loadImage();
  } catch (e) {
    return null;
  }
}

function message(title, detail) {
  const w = new ListWidget();
  w.backgroundGradient = mist();
  text(w, title, Font.heavyRoundedSystemFont(16), ink, 2);
  w.addSpacer(4);
  text(w, detail, Font.mediumRoundedSystemFont(12), ink2, 4);
  return w;
}

function lockScreen(d) {
  const w = new ListWidget();
  w.url = BASE + "/";
  const summary = d.due ? `${d.due} to do` + (d.overdue ? `, ${d.overdue} overdue` : "") : "All clear 😻";
  if (family === "accessoryInline") {
    w.addText(`🧹 ${summary}`);
  } else if (family === "accessoryCircular") {
    text(w, d.overdue ? "🙀" : d.due ? "😼" : "😻", Font.systemFont(16), Color.white(), 1).centerAlignText();
    text(w, String(d.due), Font.heavyRoundedSystemFont(20), Color.white(), 1).centerAlignText();
  } else {
    text(w, summary, Font.heavyRoundedSystemFont(14), Color.white(), 1);
    for (const it of d.items.slice(0, 2)) text(w, `${it.sticker} ${it.title}`, Font.mediumRoundedSystemFont(12), Color.white(), 1);
    if (!d.items.length && d.next) text(w, `Next: ${d.next.title}, ${d.next.when}`, Font.mediumRoundedSystemFont(12), Color.white(), 2);
  }
  return w;
}

async function homeScreen(d) {
  const small = family === "small";
  const rows = { small: 2, medium: 3, large: 8, extraLarge: 8 }[family] || 3;
  const w = new ListWidget();
  w.url = BASE + "/";
  w.backgroundGradient = mist();
  w.setPadding(14, 16, 12, 16);
  w.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000);

  // Headline and the mood cat, same as the app's header.
  const top = w.addStack();
  top.centerAlignContent();
  const heading = top.addStack();
  heading.layoutVertically();
  text(heading, d.headline, Font.heavyRoundedSystemFont(small ? 16 : 19), ink, 2).minimumScaleFactor = 0.7;
  if (d.overdue) text(heading, `${d.overdue} overdue`, Font.boldRoundedSystemFont(12), rose, 1);
  top.addSpacer();
  const cat = await image(d.mood_image);
  if (cat) top.addImage(cat).imageSize = new Size(small ? 36 : 44, small ? 36 : 44);
  w.addSpacer(small ? 6 : 8);

  if (!d.items.length) {
    const line = d.next ? `Next up: ${d.next.sticker} ${d.next.title}, ${d.next.when}` : "Nothing planned. Only nap.";
    text(w, line, Font.semiboldRoundedSystemFont(13), ink2, 2);
  }
  // Overdue first, then yours, then shared, then the other person's.
  for (const it of d.items.slice(0, rows)) {
    const row = w.addStack();
    row.centerAlignContent();
    row.spacing = 6;
    text(row, it.sticker, Font.systemFont(small ? 13 : 15), ink, 1);
    text(row, it.title, Font.semiboldRoundedSystemFont(small ? 12 : 14), ink, 1);
    if (!small) {
      row.addSpacer();
      text(row, it.when, Font.mediumRoundedSystemFont(12), it.late ? rose : ink2, 1);
    }
    w.addSpacer(small ? 3 : 5);
  }
  if (d.items.length > rows) text(w, `+${d.items.length - rows} more`, Font.boldRoundedSystemFont(11), ink2, 1);
  w.addSpacer();
  return w;
}

let widget;
try {
  const d = await new Request(`${BASE}/api/widget?key=${KEY}`).loadJSON();
  if (d.error) widget = message("Chores", d.error);
  else widget = family.startsWith("accessory") ? lockScreen(d) : await homeScreen(d);
} catch (e) {
  widget = message("Can't reach Chores", "No connection right now. The widget tries again in a few minutes.");
}
if (config.runsInWidget || config.runsInAccessoryWidget) Script.setWidget(widget);
else await widget.presentMedium();
Script.complete();
