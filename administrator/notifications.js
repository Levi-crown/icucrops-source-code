// See user/notifications.js for the measurements: painting every alert cost
// ~836ms at 429 items on the kiosk Pi, and every arriving alert repaints the
// whole list again while the drawer is open.
const NOTIFICATION_DRAWER_RENDER_LIMIT = 50;

function notificationDrawerTemplate() {
  const sortedNotifications = [...state.notifications].sort(
    (left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime()
  );
  const notifications = sortedNotifications.slice(0, NOTIFICATION_DRAWER_RENDER_LIMIT);
  const hiddenCount = sortedNotifications.length - notifications.length;

  return `
    <div class="overlay overlay--drawer">
      <aside class="drawer">
        <div class="drawer__header">
          <div>
            <h3 class="section-title">Notifications</h3>
            <p class="section-copy">Open alerts and recent dashboard activity.</p>
          </div>
          <button class="icon-button" type="button" data-action="close-notifications">
            ${icon("close")}
          </button>
        </div>

        <div class="drawer__hero notification-drawer__hero">
          <div class="section-copy">Alert Overview</div>
          <p class="drawer__hero-value">${state.notifications.length} <span>active alerts</span></p>
          <p class="section-copy">Unread in history: ${unreadNotificationCount()}</p>
        </div>

        ${notifications.length ? `
          <div class="notification-list notification-list--compact">
            ${notifications.map((notification) => notificationItemTemplate(notification)).join("")}
          </div>
          ${hiddenCount > 0 ? `
            <p class="section-copy notification-list__truncated">
              Showing the ${notifications.length} most recent of ${sortedNotifications.length}.
              Open View History for the rest.
            </p>
          ` : ""}
        ` : `
          <div class="center-banner">No active notifications right now.</div>
        `}

        <div class="drawer__actions">
          <button class="button button--secondary button--full" type="button" data-action="close-notifications">
            Close
          </button>
          <button class="button button--primary button--full" type="button" data-view="history">
            ${icon("history")}
            <span>View History</span>
          </button>
        </div>
      </aside>
    </div>
  `;
}

function notificationItemTemplate(notification, showNewBadge = false) {
  return `
    <article class="notification-item notification-item--${notification.type}">
      <div class="notification-item__meta">
        <span class="notification-item__icon">${icon(toastIconName(notification.type))}</span>
        <div class="notification-item__content">
          <div class="notification-item__row">
            <p class="notification-item__title">${escapeHtml(notification.message)}</p>
            ${showNewBadge && !notification.read ? '<span class="notification-item__badge">New</span>' : ""}
          </div>
          <p class="notification-item__time">${escapeHtml(formatNotificationTimestamp(notification.createdAt))}</p>
        </div>
      </div>
      <div class="notification-item__actions">
        <span class="pill ${notificationPillClass(notification.type)}">${escapeHtml(capitalize(notification.type))}</span>
        <button
          class="icon-button icon-button--danger notification-item__delete"
          type="button"
          data-action="delete-notification"
          data-id="${escapeHtml(notification.id)}"
          aria-label="Delete notification"
          title="Delete notification"
        >
          ${icon("trash")}
        </button>
      </div>
    </article>
  `;
}

function toastTemplate(notification) {
  return `
    <div class="toast toast--${notification.type} ${notification.exiting ? "is-exiting" : ""}">
      <span class="toast__icon toast__icon--${notification.type}">${icon(toastIconName(notification.type))}</span>
      <div class="toast__body">
        <div class="toast__meta">
          <span class="toast__eyebrow">${escapeHtml(capitalize(notification.type))}</span>
          <span class="toast__time">${escapeHtml(formatNotificationTimestamp(notification.createdAt))}</span>
        </div>
        <p class="toast__title">${escapeHtml(notification.message)}</p>
      </div>
      <button
        class="icon-button toast__dismiss"
        type="button"
        data-action="dismiss-toast"
        data-id="${notification.id}"
        aria-label="Dismiss notification"
      >
        ${icon("close")}
      </button>
    </div>
  `;
}

// Feedback that only confirms an action the user just took -- above all the
// result of deleting notification history -- must never become a history
// record itself. Writing one meant "Delete All" always left a fresh entry
// behind, so the page never reached the empty state the button promises and
// the kiosk, which nobody can reload by hand, looked like the delete failed.
function pushTransientNotification(type, message) {
  pushNotification(type, message, { transient: true });
}

// Clearing the history must clear what is already floating over the page too.
// Leaving the old toasts up means the alerts the user just deleted are still
// on screen, which on the kiosk -- where there is no reload to fall back on --
// reads as the delete having done nothing.
function dismissAllToasts() {
  clearAllNotificationTimers();
  state.toasts = [];
  renderToasts();
}

function pushNotification(type, message, options = {}) {
  const transient = Boolean(options && options.transient);
  const createdAt = new Date().toISOString();
  const notification = {
    id: `note-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    type,
    message,
    createdAt,
    read: false,
    exiting: false,
  };

  const recentDuplicate = state.notificationHistory.some((item) => {
    const sameMessage = item.message === notification.message && item.type === notification.type;
    const ageMs = Math.abs(new Date(item.createdAt).getTime() - new Date(createdAt).getTime());
    return sameMessage && ageMs < 5000;
  });

  if (!transient && !recentDuplicate) {
    const historyRecord = {
      id: notification.id,
      type: notification.type,
      message: notification.message,
      createdAt: notification.createdAt,
      read: state.notificationsOpen,
    };
    state.notificationHistory = [historyRecord, ...state.notificationHistory];
    state.notifications = state.notificationsOpen
      ? state.notifications
      : [historyRecord, ...state.notifications];
    renderHeader();
    if (state.activeView === "history") {
      renderPage();
    }
    if (state.notificationsOpen) {
      renderOverlays();
    }
  }

  state.toasts = [...state.toasts, notification];
  renderToasts();

  if (state.isAuthenticated && !state.notificationsOpen) {
    startNotificationTimer(notification.id);
  }
}

function startNotificationTimer(id) {
  clearNotificationTimer(id);
  const timer = window.setTimeout(() => beginNotificationExit(id), 5000);
  notificationTimers.set(id, timer);
}

function beginNotificationExit(id) {
  const notification = state.toasts.find((item) => item.id === id);
  if (!notification || notification.exiting) {
    return;
  }

  notification.exiting = true;
  renderToasts();
  clearNotificationTimer(id);

  const timer = window.setTimeout(() => {
    state.toasts = state.toasts.filter((item) => item.id !== id);
    renderToasts();
    notificationTimers.delete(id);
  }, 240);

  notificationTimers.set(id, timer);
}

function clearNotificationTimer(id) {
  const timer = notificationTimers.get(id);
  if (timer) {
    window.clearTimeout(timer);
    notificationTimers.delete(id);
  }
}

function clearAllNotificationTimers() {
  notificationTimers.forEach((timer) => window.clearTimeout(timer));
  notificationTimers.clear();
  state.toasts = state.toasts.filter((notification) => !notification.exiting);
}

function restartDashboardNotificationTimers() {
  clearAllNotificationTimers();
  if (!state.isAuthenticated || state.notificationsOpen) {
    renderToasts();
    return;
  }

  renderToasts();
  state.toasts.forEach((notification) => startNotificationTimer(notification.id));
}

function sortedNotificationHistory() {
  return [...state.notificationHistory].sort(
    (left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime()
  );
}

function unreadNotificationCount() {
  return state.notificationHistory.filter((notification) => !notification.read).length;
}

function markAllNotificationsRead(shouldRender = true) {
  let hasChanges = false;
  const unreadNotificationIds = [];

  state.notificationHistory = state.notificationHistory.map((notification) => {
    if (notification.read) {
      return notification;
    }

    hasChanges = true;
    unreadNotificationIds.push(notification.id);
    return {
      ...notification,
      read: true,
    };
  });

  state.notifications = [];

  const syncableNotificationIds = unreadNotificationIds.filter((id) => /^\d+$/.test(String(id)));

  if (!shouldRender || !hasChanges) {
    if (syncableNotificationIds.length && typeof syncNotificationReadState === "function") {
      void syncNotificationReadState(syncableNotificationIds);
    }
    return;
  }

  renderHeader();
  if (state.activeView === "history") {
    renderPage();
  }
  if (state.notificationsOpen) {
    renderOverlays();
  }

  if (syncableNotificationIds.length && typeof syncNotificationReadState === "function") {
    void syncNotificationReadState(syncableNotificationIds);
  }
}
