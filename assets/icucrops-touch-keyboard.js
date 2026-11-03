(function installICuCropsTouchKeyboard(global) {
  "use strict";

  if (global.ICuCropsTouchKeyboard?.installed) {
    return;
  }

  const ELIGIBLE_INPUT_TYPES = new Set(["text", "email", "password", "search", "tel", "url", "number"]);
  const SELECTION_RANGE_TYPES = new Set(["text", "password", "search", "tel", "url"]);
  // email and number both report a real caret position (selectionStart is
  // readable) but throw on setSelectionRange -- Chromium considers them
  // "not a text control" for editing purposes. Swapping to type="text" while
  // this keyboard is actually driving the field is what lets a tap into the
  // middle of "hachicrown@gmail.com" actually insert there instead of
  // silently falling back to appending at the end.
  const SWAP_TO_TEXT_TYPES = new Set(["email", "number"]);

  const ROWS_LOWER = [
    ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
    ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
    ["⇧", "z", "x", "c", "v", "b", "n", "m", "⌫"],
  ];
  const ROWS_UPPER = ROWS_LOWER.map((row) =>
    row.map((key) => (key.length === 1 && /[a-z]/.test(key) ? key.toUpperCase() : key)),
  );
  const ROWS_SYMBOLS = [
    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
    ["@", "#", "$", "_", "&", "-", "+", "(", ")", "/"],
    ["=", "\\", "*", '"', "'", ":", ";", "!", "?", "⌫"],
  ];
  const ROWS_NUMERIC = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    [".", "0", "⌫"],
  ];

  let root = null;
  let keysContainer = null;
  let activeTarget = null;
  let shiftOn = false;
  let symbolsOn = false;
  let numericOnly = false;
  // The type this field is supposed to have once editing ends -- null means
  // the field's own type already supports selection and was never touched.
  let swappedFromType = null;

  function isEligibleField(element) {
    if (!(element instanceof HTMLElement)) {
      return false;
    }
    if (element.closest("#icucrops-touch-keyboard")) {
      return false;
    }
    if (element.disabled || element.readOnly) {
      return false;
    }
    if (element.tagName === "TEXTAREA") {
      return true;
    }
    if (element.tagName !== "INPUT") {
      return false;
    }
    const type = (element.getAttribute("type") || "text").toLowerCase();
    return ELIGIBLE_INPUT_TYPES.has(type);
  }

  function isNumericField(element) {
    if (element.tagName === "INPUT" && (element.getAttribute("type") || "").toLowerCase() === "number") {
      return true;
    }
    const inputMode = (element.getAttribute("inputmode") || "").toLowerCase();
    return inputMode === "numeric" || inputMode === "decimal";
  }

  function supportsSelectionRange(element) {
    if (element.tagName === "TEXTAREA") {
      return true;
    }
    const type = (element.getAttribute("type") || "text").toLowerCase();
    return SELECTION_RANGE_TYPES.has(type);
  }

  function dispatchInput(element) {
    element.dispatchEvent(new Event("input", { bubbles: true }));
  }

  // The OTP boxes -- Add New User, the profile's password change, Forgot
  // Password -- each hold one digit. A physical keyboard never meets a full
  // box there: the pages select() a box's digit as they focus it, so the next
  // key replaces it. Here that selection is collapsed straight to a caret
  // (collapseSelectionIn, against the Cut/Copy bar), and insertText ignores
  // maxlength, so re-typing a box glued the new digit onto the old one -- "35"
  // in one box, which the pages then spread across two boxes or cut back to
  // the old digit. A digit typed into one of these boxes simply replaces it.
  function isSingleCharacterBox(element) {
    return element instanceof HTMLInputElement
      && (element.maxLength === 1 || element.classList.contains("otp-input"));
  }

  function insertText(text) {
    if (!activeTarget) {
      return;
    }
    if (isSingleCharacterBox(activeTarget)) {
      activeTarget.value = text;
      if (supportsSelectionRange(activeTarget)) {
        activeTarget.setSelectionRange(text.length, text.length);
      }
      dispatchInput(activeTarget);
      return;
    }
    if (supportsSelectionRange(activeTarget)) {
      const start = activeTarget.selectionStart ?? activeTarget.value.length;
      const end = activeTarget.selectionEnd ?? activeTarget.value.length;
      const value = activeTarget.value;
      activeTarget.value = value.slice(0, start) + text + value.slice(end);
      const nextPosition = start + text.length;
      activeTarget.setSelectionRange(nextPosition, nextPosition);
    } else {
      activeTarget.value += text;
    }
    dispatchInput(activeTarget);
  }

  function backspace() {
    if (!activeTarget) {
      return;
    }
    // Clears the digit wherever the caret sits in the box -- a tap on its left
    // edge left the caret in front of the digit, where backspace found nothing
    // to remove. An already-empty box still reports the press as an "input",
    // because that is the only event the OTP pages can hear from this keyboard
    // (it never sends keydown) and they use an empty box to step back.
    if (isSingleCharacterBox(activeTarget)) {
      activeTarget.value = "";
      dispatchInput(activeTarget);
      return;
    }
    if (supportsSelectionRange(activeTarget)) {
      const start = activeTarget.selectionStart ?? activeTarget.value.length;
      const end = activeTarget.selectionEnd ?? activeTarget.value.length;
      const value = activeTarget.value;
      if (start === end) {
        if (start === 0) {
          return;
        }
        activeTarget.value = value.slice(0, start - 1) + value.slice(end);
        activeTarget.setSelectionRange(start - 1, start - 1);
      } else {
        activeTarget.value = value.slice(0, start) + value.slice(end);
        activeTarget.setSelectionRange(start, start);
      }
    } else {
      activeTarget.value = activeTarget.value.slice(0, -1);
    }
    dispatchInput(activeTarget);
  }

  const KEY_REPEAT_DELAY_MS = 450;
  const KEY_REPEAT_INTERVAL_MS = 90;
  // Only backspace runs on while held, as on a phone keyboard. Every other key
  // types once per press however long the finger stays down. Letters used to
  // repeat too, and a press held past KEY_REPEAT_DELAY_MS -- routine on this
  // panel, where a key answers late and people press until it does -- typed
  // the character again. In a password field that is invisible behind the
  // dots: "Abc12345!" held at ~0.55s per key arrived as "AAbbcc1122334455!!",
  // so a correct Wi-Fi or account password was always refused at the kiosk
  // and accepted everywhere else.
  const REPEATING_KEYS = new Set(["⌫"]);
  let keyHoldTimer = null;
  let keyRepeatTimer = null;

  function stopKeyRepeat() {
    if (keyHoldTimer !== null) {
      global.clearTimeout(keyHoldTimer);
      keyHoldTimer = null;
    }
    if (keyRepeatTimer !== null) {
      global.clearInterval(keyRepeatTimer);
      keyRepeatTimer = null;
    }
  }

  // The press itself has already deleted one character by the time this
  // runs, so a quick tap deletes once and only a genuine press-and-hold keeps
  // deleting.
  function startKeyRepeat() {
    stopKeyRepeat();
    keyHoldTimer = global.setTimeout(() => {
      keyHoldTimer = null;
      keyRepeatTimer = global.setInterval(backspace, KEY_REPEAT_INTERVAL_MS);
    }, KEY_REPEAT_DELAY_MS);
  }

  // A number input rejects an in-progress value like "12." outright -- typing
  // the "." is normal mid-entry, but restoring type="number" on a value the
  // browser considers invalid silently blanks the whole field. Trimming back
  // to the longest valid prefix keeps whatever the farmer already typed
  // instead of losing it the moment they move to the next field.
  function sanitizeForNumberType(rawValue) {
    const match = rawValue.match(/^-?\d*\.?\d*/);
    let candidate = match ? match[0] : "";
    if (candidate.endsWith(".")) {
      candidate = candidate.slice(0, -1);
    }
    if (candidate === "-") {
      candidate = "";
    }
    return candidate;
  }

  function beginEditing(target) {
    swappedFromType = null;
    if (!(target instanceof HTMLInputElement)) {
      return;
    }
    const type = (target.getAttribute("type") || "text").toLowerCase();
    if (!SWAP_TO_TEXT_TYPES.has(type)) {
      return;
    }
    swappedFromType = type;
    // Chromium rebuilds the field's inner editor when the type changes, and
    // the rebuilt one starts with its caret at 0 -- so on an email or number
    // field that already holds text, opening the keyboard silently parked the
    // caret in front of the first character. Every key then typed inserted at
    // the very start of the value, and backspace found nothing before the
    // caret to remove, which is why it did nothing at all whether it was
    // tapped or held down. Put the caret at the end, where focusing a field on
    // a physical keyboard leaves it; a tap into the text still moves it from
    // there, because the tap's native caret placement runs after this.
    let caret = null;
    try {
      caret = target.selectionStart;
    } catch {
      caret = null;
    }
    target.setAttribute("type", "text");
    const end = target.value.length;
    const position = typeof caret === "number" ? Math.min(caret, end) : end;
    try {
      target.setSelectionRange(position, position);
    } catch {
      // A field that still refuses a caret keeps the append-at-end fallback
      // in insertText/backspace rather than breaking the keypress outright.
    }
  }

  function endEditing(target) {
    if (!swappedFromType || !(target instanceof HTMLInputElement)) {
      swappedFromType = null;
      return;
    }
    if (swappedFromType === "number") {
      const sanitized = sanitizeForNumberType(target.value);
      if (sanitized !== target.value) {
        target.value = sanitized;
        dispatchInput(target);
      }
    }
    target.setAttribute("type", swappedFromType);
    swappedFromType = null;
  }

  function setActiveTarget(target) {
    if (activeTarget === target) {
      return;
    }
    if (activeTarget) {
      endEditing(activeTarget);
    }
    activeTarget = target;
    numericOnly = target ? isNumericField(target) : false;
    if (target) {
      beginEditing(target);
    }
  }

  function buildKeyButton(label, key) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "icucrops-tk__key";
    button.dataset.key = key;
    button.textContent = label;
    if (key === "⇧") {
      button.classList.add("icucrops-tk__key--shift");
    } else if (key === "⌫") {
      button.classList.add("icucrops-tk__key--wide");
    }
    return button;
  }

  function renderNumericKeys() {
    ROWS_NUMERIC.forEach((row) => {
      const rowElement = document.createElement("div");
      rowElement.className = "icucrops-tk__row";
      row.forEach((key) => {
        rowElement.appendChild(buildKeyButton(key, key));
      });
      keysContainer.appendChild(rowElement);
    });

    const bottomRow = document.createElement("div");
    bottomRow.className = "icucrops-tk__row";
    const enterKey = document.createElement("button");
    enterKey.type = "button";
    enterKey.className = "icucrops-tk__key icucrops-tk__key--wide icucrops-tk__key--enter";
    enterKey.dataset.key = "Enter";
    enterKey.textContent = "Done";
    bottomRow.appendChild(enterKey);
    keysContainer.appendChild(bottomRow);
  }

  function renderKeys() {
    if (!keysContainer) {
      return;
    }
    keysContainer.innerHTML = "";

    if (numericOnly) {
      renderNumericKeys();
      return;
    }

    const rows = symbolsOn ? ROWS_SYMBOLS : shiftOn ? ROWS_UPPER : ROWS_LOWER;
    rows.forEach((row) => {
      const rowElement = document.createElement("div");
      rowElement.className = "icucrops-tk__row";
      row.forEach((key) => {
        const label = key === "⇧" ? (shiftOn ? "⇧✓" : "⇧") : key;
        rowElement.appendChild(buildKeyButton(label, key));
      });
      keysContainer.appendChild(rowElement);
    });

    const bottomRow = document.createElement("div");
    bottomRow.className = "icucrops-tk__row";
    const symbolsToggle = document.createElement("button");
    symbolsToggle.type = "button";
    symbolsToggle.className = "icucrops-tk__key icucrops-tk__key--wide";
    symbolsToggle.dataset.key = "SymbolsToggle";
    symbolsToggle.textContent = symbolsOn ? "ABC" : "123";
    bottomRow.appendChild(symbolsToggle);

    const atKey = buildKeyButton("@", "@");
    bottomRow.appendChild(atKey);

    const spaceKey = document.createElement("button");
    spaceKey.type = "button";
    spaceKey.className = "icucrops-tk__key icucrops-tk__key--space";
    spaceKey.dataset.key = " ";
    spaceKey.textContent = "Space";
    bottomRow.appendChild(spaceKey);

    const dotKey = buildKeyButton(".", ".");
    bottomRow.appendChild(dotKey);

    const enterKey = document.createElement("button");
    enterKey.type = "button";
    enterKey.className = "icucrops-tk__key icucrops-tk__key--wide icucrops-tk__key--enter";
    enterKey.dataset.key = "Enter";
    enterKey.textContent = "Done";
    bottomRow.appendChild(enterKey);

    keysContainer.appendChild(bottomRow);
  }

  function buildRoot() {
    const element = document.createElement("div");
    element.id = "icucrops-touch-keyboard";
    element.className = "icucrops-tk";
    element.hidden = true;

    const header = document.createElement("div");
    header.className = "icucrops-tk__header";
    const title = document.createElement("span");
    title.className = "icucrops-tk__title";
    title.textContent = "Keyboard";
    header.appendChild(title);
    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.className = "icucrops-tk__close";
    closeButton.dataset.key = "Hide";
    closeButton.setAttribute("aria-label", "Hide keyboard");
    closeButton.textContent = "✕";
    header.appendChild(closeButton);
    element.appendChild(header);

    keysContainer = document.createElement("div");
    keysContainer.className = "icucrops-tk__keys";
    element.appendChild(keysContainer);

    // Keys act on the press itself rather than on a click. A finger on the
    // panel always drifts a pixel or two and is often held a beat longer than
    // a mouse click, and either one lets the browser read the press as the
    // start of a pan gesture -- in which case it cancels the pointer stream
    // and no click is ever produced. That is what left the ⌫ key looking
    // dead: the press was real, the click that was supposed to carry it out
    // never arrived.
    element.addEventListener("pointerdown", (event) => {
      // Keep focus, and therefore the caret, on the real field; a virtual key
      // must never steal it.
      event.preventDefault();
      const keyButton = event.target.closest("[data-key]");
      if (!keyButton) {
        return;
      }
      // Defensive: a previous hold's pointerup/pointercancel can be missed by
      // the touch driver, which would otherwise leave that key's repeat timer
      // running forever underneath whatever gets typed next. A fresh press
      // always starts from a clean slate.
      stopKeyRepeat();
      const key = keyButton.dataset.key;
      handleKey(key);
      if (REPEATING_KEYS.has(key)) {
        startKeyRepeat();
      }
    });

    document.body.appendChild(element);
    return element;
  }

  function handleKey(key) {
    if (!activeTarget || !activeTarget.isConnected) {
      hideKeyboard();
      return;
    }
    switch (key) {
      case "Hide":
        hideKeyboard();
        return;
      case "⇧":
        shiftOn = !shiftOn;
        renderKeys();
        return;
      case "SymbolsToggle":
        symbolsOn = !symbolsOn;
        renderKeys();
        return;
      case "⌫":
        backspace();
        return;
      case "Enter": {
        const field = activeTarget;
        const form = field.form;
        hideKeyboard();
        if (form && typeof form.requestSubmit === "function") {
          form.requestSubmit();
        } else {
          field.blur();
        }
        return;
      }
      default:
        insertText(key);
        if (shiftOn && key !== " " && !symbolsOn) {
          shiftOn = false;
          renderKeys();
        }
        return;
    }
  }

  // The keyboard is a fixed overlay on top of the page, not a layout push, so
  // nothing shrinks the space a field can scroll into by default -- a field
  // scrolled to screen-center can still end up sitting entirely underneath
  // the keyboard panel on the kiosk's 800x480 display, where the panel alone
  // covers most of the vertical space. Recording its real height as a CSS
  // custom property lets `scroll-margin-bottom` on the field (see
  // icucrops-touch-keyboard.css) keep it clear of the panel automatically,
  // for whichever ancestor actually scrolls.
  function updateKeyboardHeightVar() {
    if (!root) {
      return;
    }
    const height = root.getBoundingClientRect().height;
    document.documentElement.style.setProperty("--icucrops-tk-height", `${height}px`);
  }

  // How much clear space to leave between the field and the panel's top edge.
  const FIELD_CLEARANCE_PX = 12;
  // The scroller we padded, so the page can be put back exactly as found.
  let reservedScroller = null;
  let reservedPreviousPadding = "";
  let reservedPreviousPriority = "";
  let reservedPreviousTransition = "";
  let reservedPreviousTransitionPriority = "";
  // Extra room added when padding alone did not make the scroller scroll: a
  // ::after sized by a custom property, switched on by an attribute (see
  // installRoomStyle).
  const ROOM_ATTRIBUTE = "data-icucrops-tk-room";
  const ROOM_HEIGHT_PROPERTY = "--icucrops-tk-room";
  let reservedRoomHeight = 0;
  // What grid-auto-rows held before a grid scroller's rows were pinned at
  // their natural height for the reservation (see holdGridRowsIfSquashed).
  let reservedHeldRows = null;

  // A dialog is `.overlay`, `position: fixed`, so nothing above it scrolls it
  // -- the box sits at the same spot regardless of how far the document has
  // scrolled. A short dialog whose own content fits inside its max-height
  // never overflows either, so a field low in it has no scroller anywhere in
  // its ancestry that could move it clear of the panel. Measured on the
  // Custom Parameters editor at 800x480: five short fields, nowhere near tall
  // enough to make .modal__body scroll, with the EC row sitting under the
  // panel and nothing above it able to move. Translating the fixed ancestor
  // itself is what covers that gap; the state below is what puts it back.
  let liftedFixedAncestor = null;
  let liftedAmount = 0;
  let liftedPreviousTransform = "";
  let liftedPreviousPriority = "";
  let liftedPreviousTransition = "";
  let liftedPreviousTransitionPriority = "";

  function fixedAncestorOf(element) {
    let node = element.parentElement;
    while (node && node !== document.body && node !== document.documentElement) {
      if (global.getComputedStyle(node).position === "fixed") {
        return node;
      }
      node = node.parentElement;
    }
    return null;
  }

  function releaseModalLift() {
    if (!liftedFixedAncestor) {
      return;
    }
    if (liftedPreviousTransform) {
      liftedFixedAncestor.style.setProperty("transform", liftedPreviousTransform, liftedPreviousPriority);
    } else {
      liftedFixedAncestor.style.removeProperty("transform");
    }
    // Transform settled first, transition second -- the same order the
    // padding revert needs (candidateGainsRoomFromPadding), or the removal
    // itself glides for 150ms and the next measurement reads a dialog still
    // half-lifted.
    void global.getComputedStyle(liftedFixedAncestor).transform;
    if (liftedPreviousTransition) {
      liftedFixedAncestor.style.setProperty("transition", liftedPreviousTransition, liftedPreviousTransitionPriority);
    } else {
      liftedFixedAncestor.style.removeProperty("transition");
    }
    liftedFixedAncestor = null;
    liftedAmount = 0;
    liftedPreviousTransform = "";
    liftedPreviousPriority = "";
    liftedPreviousTransition = "";
    liftedPreviousTransitionPriority = "";
  }

  // A declared overflow is not enough on its own, because CSS hands out
  // "auto" for free: a box with overflow-x: hidden and no overflow-y of its
  // own computes overflow-y: auto, per spec. Several cards in this app are
  // exactly that, and one of them is the parameter card the EC field sits in.
  //
  // Treating it as a scroller was what broke the custom-parameter dialog on
  // the 800x480 panel. It is the innermost match, so it took the room the
  // keyboard reserves -- while .modal__body, the box that could actually lift
  // the field, got none and was already scrolled to its end. EC is the last of
  // the five cards, so the field ended up at y=548 on a 480px screen: entirely
  // below the panel, with the farmer typing into something they could not see.
  //
  // Requiring real overflow tells the two apart. A card that fits its own
  // contents cannot lift anything, and scrolling it would only move the
  // field's interior.
  function isScrollableBox(node) {
    const overflowY = global.getComputedStyle(node).overflowY;
    if (overflowY !== "auto" && overflowY !== "scroll" && overflowY !== "overlay") {
      return false;
    }
    return node.scrollHeight > node.clientHeight;
  }

  // Inside the app the page does not scroll at all -- the dashboard scrolls
  // within .page-content, and dialogs within .modal__body -- so padding the
  // body and scrolling the window, which is all the login screen needs, moves
  // nothing on any screen reached after signing in.
  function scrollableAncestorsOf(element) {
    const chain = [];
    let node = element.parentElement;
    while (node && node !== document.body && node !== document.documentElement) {
      if (isScrollableBox(node)) {
        chain.push(node);
      }
      node = node.parentElement;
    }
    return chain;
  }

  // A box that is not currently scrolling is not necessarily one that never
  // can. .page-content on the kiosk has a real, fixed height and a declared
  // overflow-y: auto -- it just does not always have enough content to need
  // it, the way the Irrigation row card's Manual controls (one field) reads
  // as short next to its Schedule controls (three). scrollableAncestorsOf
  // above correctly refuses to guess at that from overflow-y alone, because
  // the same computed value also shows up on a box that is only auto by the
  // overflow-x: hidden side effect Trap 1 above already tells apart -- and
  // unlike .page-content, that box's height grows with its own content, so
  // padding it would just make it taller instead of creating room to scroll
  // into. The two cannot be told apart from overflow-y alone; they can be
  // told apart by trying the pad and checking whether it actually grew
  // scrollHeight past clientHeight instead of both together.
  function ancestorsWithDeclaredOverflowOf(element) {
    const candidates = [];
    let node = element.parentElement;
    while (node && node !== document.body && node !== document.documentElement) {
      const overflowY = global.getComputedStyle(node).overflowY;
      if (overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay") {
        candidates.push(node);
      }
      node = node.parentElement;
    }
    return candidates;
  }

  function childHeightsOf(node) {
    return Array.from(node.children, (child) => child.getBoundingClientRect().height);
  }

  // Padding shrinks a grid's content box, and a grid fits its auto rows
  // into that box. A row whose item is itself a scroll container (overflow
  // hidden, as the glass cards are) has no content-based minimum, so it
  // gives the space up. The Add New User OTP step's .modal__body is exactly
  // that: its step card went from 236px to 28px under the reservation, it
  // clipped the code boxes to slivers -- the "broken" boxes photographed on
  // the panel -- and the padding bought 36px of scroll instead of 286px.
  // Holding the rows at their natural height puts the content back and
  // makes the padding real room below it. Returns what to restore, or null
  // when nothing shrank or the box is not a grid.
  function holdGridRowsIfSquashed(node, heightsBefore) {
    const shrank = Array.from(node.children).some((child, index) =>
      child.getBoundingClientRect().height < (heightsBefore[index] ?? 0) - 1);
    if (!shrank || !global.getComputedStyle(node).display.endsWith("grid")) {
      return null;
    }
    const previous = {
      value: node.style.getPropertyValue("grid-auto-rows"),
      priority: node.style.getPropertyPriority("grid-auto-rows"),
    };
    node.style.setProperty("grid-auto-rows", "max-content", "important");
    void node.offsetHeight;
    return previous;
  }

  function restoreGridRows(node, previous) {
    if (previous.value) {
      node.style.setProperty("grid-auto-rows", previous.value, previous.priority);
    } else {
      node.style.removeProperty("grid-auto-rows");
    }
  }

  // Tries the pad-and-check above without leaving the candidate modified
  // either way -- reserveRoomForActiveField reapplies for real, with proper
  // state tracking, on whichever candidate this returns true for.
  function candidateGainsRoomFromPadding(node, panelHeight) {
    const previousTransition = node.style.getPropertyValue("transition");
    const previousTransitionPriority = node.style.getPropertyPriority("transition");
    const previousPadding = node.style.getPropertyValue("padding-bottom");
    const previousPaddingPriority = node.style.getPropertyPriority("padding-bottom");
    // Transition off first, so a padding still gliding (see
    // reserveRoomForActiveField) is read at its settled value.
    node.style.setProperty("transition", "none", "important");
    const existing = parseFloat(global.getComputedStyle(node).paddingBottom) || 0;
    const heightsBefore = childHeightsOf(node);
    node.style.setProperty("padding-bottom", `${existing + panelHeight}px`, "important");
    void node.offsetHeight;
    // Tried the way the real reservation will apply it: a grid that gave up
    // its rows to the padding looks as if it gained nothing, when holding the
    // rows (below) is what turns that padding into room.
    const heldRows = holdGridRowsIfSquashed(node, heightsBefore);
    const gained = node.scrollHeight > node.clientHeight;
    // Padding first, transition second: restoring both together would let
    // the wildcard's freshly-reinstated transition apply to the padding's
    // own removal, leaving a stale, still-padded computed value in place
    // for whoever reads this node's padding right after this call returns
    // -- reserveRoomForActiveField's own "existing" measurement, doubling
    // the reservation on top of a number that no longer described anything.
    if (heldRows) {
      restoreGridRows(node, heldRows);
    }
    if (previousPadding) {
      node.style.setProperty("padding-bottom", previousPadding, previousPaddingPriority);
    } else {
      node.style.removeProperty("padding-bottom");
    }
    void node.offsetHeight;
    if (previousTransition) {
      node.style.setProperty("transition", previousTransition, previousTransitionPriority);
    } else {
      node.style.removeProperty("transition");
    }
    return gained;
  }

  function declaredScrollableAncestorNeedingRoom(element, panelHeight) {
    return ancestorsWithDeclaredOverflowOf(element).find((candidate) =>
      candidateGainsRoomFromPadding(candidate, panelHeight));
  }

  function releaseReservedRoom() {
    releaseModalLift();
    if (!reservedScroller) {
      return;
    }
    if (reservedPreviousPadding) {
      reservedScroller.style.setProperty(
        "padding-bottom",
        reservedPreviousPadding,
        reservedPreviousPriority,
      );
    } else {
      reservedScroller.style.removeProperty("padding-bottom");
    }
    if (reservedRoomHeight) {
      reservedScroller.removeAttribute(ROOM_ATTRIBUTE);
      reservedScroller.style.removeProperty(ROOM_HEIGHT_PROPERTY);
      reservedRoomHeight = 0;
    }
    if (reservedHeldRows) {
      restoreGridRows(reservedScroller, reservedHeldRows);
      reservedHeldRows = null;
    }
    // Settle the padding before the transition override comes off, or the
    // wildcard's 150ms transition animates its removal (see
    // candidateGainsRoomFromPadding).
    void reservedScroller.offsetHeight;
    if (reservedPreviousTransition) {
      reservedScroller.style.setProperty(
        "transition",
        reservedPreviousTransition,
        reservedPreviousTransitionPriority,
      );
    } else {
      reservedScroller.style.removeProperty("transition");
    }
    reservedScroller = null;
    reservedPreviousPadding = "";
    reservedPreviousPriority = "";
    reservedPreviousTransition = "";
    reservedPreviousTransitionPriority = "";
  }

  // A field at the bottom of its scroller has nothing below it to scroll into,
  // so making room is what allows the lift below to move anything at all. The
  // body gets this from the stylesheet; a nested scroller has to be measured
  // and padded here, since only this code knows which one holds the field.
  function reserveRoomForActiveField() {
    releaseReservedRoom();
    if (!activeTarget || !root || root.hidden) {
      return;
    }
    const panelHeight = root.getBoundingClientRect().height;
    if (!panelHeight) {
      return;
    }
    const scroller = scrollableAncestorsOf(activeTarget)[0]
      || declaredScrollableAncestorNeedingRoom(activeTarget, panelHeight);
    if (!scroller) {
      return;
    }
    reservedScroller = scroller;
    reservedPreviousPadding = scroller.style.getPropertyValue("padding-bottom");
    reservedPreviousPriority = scroller.style.getPropertyPriority("padding-bottom");
    reservedPreviousTransition = scroller.style.getPropertyValue("transition");
    reservedPreviousTransitionPriority = scroller.style.getPropertyPriority("transition");
    // Transition off *before* the existing padding is read. When an app
    // redraw has just stripped this keyboard's inline styles, the padding is
    // mid-way through a 150ms glide back down, and reading it then added the
    // old reservation onto the new one: 445px where 222px was measured.
    // Turning the transition off snaps the value to where it is headed.
    //
    // It also has to stay off for the write below: html.pi-kiosk * forces a
    // transition-duration on every element (see the matching note on the
    // fixed-ancestor lift below); with transition-property left at its
    // default `all`, that turns this padding-bottom into a 150ms animated
    // grow instead of an instant one. scrollHeight is derived from layout, so
    // it reads the old, pre-growth number until the transition finishes --
    // `remaining` below comes out zero on a field already scrolled to its old
    // limit, and the lift has no room to use even though the reservation ran
    // and, a frame later, would have given it plenty.
    scroller.style.setProperty("transition", "none", "important");
    const existing = parseFloat(global.getComputedStyle(scroller).paddingBottom) || 0;
    const childHeightsBefore = childHeightsOf(scroller);
    // !important, because a plain inline value loses to one. The dialogs in
    // this app are styled by sheets that set modal padding with !important, so
    // the reservation was being written and then ignored: the inline 347px
    // computed back as 16px, the scroller gained no room, and the lift below
    // had nothing to move. Measured on the custom-parameter dialog at 800x480.
    scroller.style.setProperty(
      "padding-bottom",
      `${existing + panelHeight}px`,
      "important",
    );
    void scroller.offsetHeight;
    reservedHeldRows = holdGridRowsIfSquashed(scroller, childHeightsBefore);
    // Whatever room the padding still failed to provide below the field is
    // made up with a spacer, which every layout counts.
    //
    // The spacer is a ::after, not an element. The app's overlay refresh
    // (morphNode) compares child counts, and one extra child made it swap out
    // the whole dialog body -- the focused OTP box included -- a second after
    // the first digit.
    const field = activeTarget.getBoundingClientRect();
    const box = scroller.getBoundingClientRect();
    const roomBelowField = scroller.scrollHeight
      - (field.bottom - box.top + scroller.scrollTop);
    const shortfall = Math.ceil(panelHeight - roomBelowField);
    if (shortfall > 0) {
      reservedRoomHeight = shortfall;
      scroller.style.setProperty(ROOM_HEIGHT_PROPERTY, `${shortfall}px`);
      scroller.setAttribute(ROOM_ATTRIBUTE, "");
    }
  }

  // scrollIntoView is no use here: every one of its block positions treats a
  // field that is merely *covered* by the panel as already visible, so it
  // scrolls nothing at all, and "center" would park the field at 240px on this
  // 480px-tall screen -- still underneath a panel whose top edge is at 206px.
  // The lift is therefore computed against the panel's own rectangle. It is
  // jumped, not animated: a tap landing while a smooth scroll is still running
  // is spent stopping that scroll, so the tap that moves the caret would go
  // missing.
  function liftActiveFieldAboveKeyboard() {
    if (!activeTarget || !root || root.hidden) {
      return;
    }
    const panelTop = root.getBoundingClientRect().top;
    const scrollers = scrollableAncestorsOf(activeTarget);

    // Innermost scroller first, then outwards, then the page itself -- the
    // same order the browser would hand a scroll gesture to.
    scrollers.forEach((scroller) => {
      const field = activeTarget.getBoundingClientRect();
      const hidden = field.bottom + FIELD_CLEARANCE_PX - panelTop;
      if (hidden <= 0) {
        return;
      }
      const box = scroller.getBoundingClientRect();
      const remaining = scroller.scrollHeight - scroller.clientHeight - scroller.scrollTop;
      // Never lift the field past the top of its own scroller, or it just
      // disappears out of the other side of the box.
      const room = Math.max(field.top - Math.max(box.top, 0) - FIELD_CLEARANCE_PX, 0);
      const delta = Math.min(hidden, Math.max(remaining, 0), room);
      if (delta > 0) {
        scroller.scrollTop += delta;
      }
    });

    const field = activeTarget.getBoundingClientRect();
    const hidden = field.bottom + FIELD_CLEARANCE_PX - panelTop;

    // Only when nothing above the field can scroll at all -- a dialog with a
    // real overflowing .modal__body already has this fully covered by the
    // loop above, and a field there is often still marginally covered after
    // its first of three attempts purely because the reservation has not
    // finished growing the scroller yet. Gating on `scrollers.length` rather
    // than "still hidden here" keeps this branch out of that case entirely,
    // instead of layering a whole-dialog translate on top of a scroll that
    // was already going to finish clearing the field on its own -- which is
    // what shifted the Irrigation, Cultivation setup, Profile, and Change
    // Password dialogs (every one of them genuinely scrollable) out of place.
    //
    // A dialog is `position: fixed`, so window.scrollBy below would move the
    // document underneath it without moving the dialog itself at all -- the
    // field would measure exactly the same on the next attempt. Translating
    // the fixed box is the only thing that reaches a field inside one.
    //
    // The one exception is a scroller that has already done all it can: the
    // field is up against its top edge, and no amount of scrolling moves it
    // higher. Add New User's form scrolls inside a short box that starts at
    // y=211 on the panel, below the dialog's header and step card; the Name
    // field pinned to its top still ended at y=262 with the keyboard's edge at
    // 257, and only moving the dialog itself shows the field. That is decided
    // by position, not by "still hidden", so a scroller still catching up on
    // its reserved room (the case above) never qualifies. Nor does a field
    // already in sight and merely inside the clearance margin: moving the
    // whole dialog for a few pixels of margin is the shift described above.
    const everyScrollerIsSpent = scrollers.length > 0
      && field.bottom > panelTop
      && scrollers.every((scroller) => {
        const box = scroller.getBoundingClientRect();
        return field.top - Math.max(box.top, 0) - FIELD_CLEARANCE_PX <= 1;
      });
    const fixedAncestor = scrollers.length === 0 || everyScrollerIsSpent
      ? fixedAncestorOf(activeTarget)
      : null;
    if (fixedAncestor) {
      if (hidden > 0) {
        if (liftedFixedAncestor !== fixedAncestor) {
          releaseModalLift();
          liftedFixedAncestor = fixedAncestor;
          liftedPreviousTransform = fixedAncestor.style.getPropertyValue("transform");
          liftedPreviousPriority = fixedAncestor.style.getPropertyPriority("transform");
          liftedPreviousTransition = fixedAncestor.style.getPropertyValue("transition");
          liftedPreviousTransitionPriority = fixedAncestor.style.getPropertyPriority("transition");
          // html.pi-kiosk * sets `transition-duration: 150ms !important` on
          // every element to keep hover/press fades short but real, and
          // `transition-property` is left at its initial `all`. That turns
          // this translate into a 150ms animated one instead of an instant
          // jump -- so the very next attempt below measures a field still
          // mid-glide, "corrects" for distance it has not actually covered
          // yet, and the two attempts left in the retry compound that into a
          // lift several times larger than the field ever needed. Only an
          // inline !important transition beats that rule; nothing weaker does.
          fixedAncestor.style.setProperty("transition", "none", "important");
        }
        // Room is measured against the viewport, not the dialog's own box:
        // `.overlay` is `inset: 0`, so its box is the full screen regardless
        // of where the centered dialog inside it actually sits, and clamping
        // against that let the field be pushed straight off the top edge.
        const room = Math.max(field.top - FIELD_CLEARANCE_PX, 0);
        const additional = Math.min(hidden, room);
        if (additional > 0) {
          liftedAmount += additional;
          fixedAncestor.style.setProperty("transform", `translateY(-${liftedAmount}px)`, liftedPreviousPriority);
        }
      }
      return;
    }

    if (hidden > 0) {
      // Never so far that the field disappears off the top instead; on a
      // screen too short to clear the panel completely, lift what we can.
      const room = Math.max(field.top - FIELD_CLEARANCE_PX, 0);
      const delta = Math.min(hidden, room);
      if (delta > 0) {
        global.scrollBy(0, delta);
      }
      return;
    }
    if (field.top < FIELD_CLEARANCE_PX) {
      global.scrollBy(0, field.top - FIELD_CLEARANCE_PX);
    }
  }

  function activeFieldIsClearOfKeyboard() {
    if (!activeTarget || !root || root.hidden) {
      return true;
    }
    const field = activeTarget.getBoundingClientRect();
    return field.bottom + FIELD_CLEARANCE_PX <= root.getBoundingClientRect().top;
  }

  // The lift is retried rather than run once. Reserving the room grows the
  // scroller, and the frame straight afterwards can still measure the old
  // scrollHeight -- caught on the panel, where the first attempt found only
  // 13px of room left instead of the 222px just added and lifted the field
  // barely at all. Each attempt scrolls only what is still missing, so
  // repeating is harmless, and it stops as soon as the field is clear.
  const LIFT_ATTEMPTS = 3;

  function settleKeyboardToActiveField() {
    updateKeyboardHeightVar();
    reserveRoomForActiveField();
    // Reading a layout property applies the reserved room now instead of at
    // the next layout pass. Without it the first attempt measures the old
    // scrollHeight -- on the panel it found 13px of room where 222px had
    // just been added -- and the field would still be creeping upwards
    // frames later, which is exactly the drift a finger reaching for the
    // text loses its target to.
    void document.body.offsetHeight;
    let attempts = 0;
    const attempt = () => {
      liftActiveFieldAboveKeyboard();
      attempts += 1;
      if (attempts < LIFT_ATTEMPTS && !activeFieldIsClearOfKeyboard()) {
        global.requestAnimationFrame(attempt);
      }
    };
    // Run straight away rather than a frame later, so the field is where it
    // is going to stay by the time the keyboard is first painted.
    attempt();
  }

  function syncKeyboardToActiveField() {
    global.requestAnimationFrame(settleKeyboardToActiveField);
  }

  // The app shells redraw open dialogs on their own timer (a live refresh
  // calls renderOverlays, which morphs the markup back to the template). That
  // morph strips every inline style it did not write -- the room reserved
  // above, the dialog lift, the email/number type swap -- and a changed shape
  // swaps a dialog's children for fresh ones, the focused field included. On
  // the panel, a second or two after the keyboard opened, the field fell back
  // under the keys or the keys went on typing into a detached box. Anything
  // the keyboard set up that a redraw took away is put back here, before the
  // next paint (mutation callbacks run ahead of it).
  let layoutObserver = null;

  function keyboardLayoutWasUndone() {
    if (!activeTarget) {
      return false;
    }
    if (!activeTarget.isConnected) {
      return true;
    }
    if (swappedFromType && (activeTarget.getAttribute("type") || "text").toLowerCase() !== "text") {
      return true;
    }
    if (reservedScroller) {
      if (!reservedScroller.isConnected
        || reservedScroller.style.getPropertyPriority("padding-bottom") !== "important") {
        return true;
      }
      if (reservedRoomHeight && !reservedScroller.hasAttribute(ROOM_ATTRIBUTE)) {
        return true;
      }
      if (reservedHeldRows
        && reservedScroller.style.getPropertyPriority("grid-auto-rows") !== "important") {
        return true;
      }
    }
    // liftedAmount, not just liftedFixedAncestor: the lift can claim a dialog
    // and then find no room to move it, and a transform that was never
    // written must not read as one a redraw took away -- that would repair,
    // write, observe and repair again without end.
    if (liftedFixedAncestor && liftedAmount > 0
      && (!liftedFixedAncestor.isConnected || !liftedFixedAncestor.style.getPropertyValue("transform"))) {
      return true;
    }
    return false;
  }

  // At most one repair per frame. Each repair writes styles, which this same
  // observer hears; should some page keep undoing it on every write, the
  // rest wait for the next frame instead of spinning inside one.
  let restoredThisFrame = false;
  let restoreDeferred = false;

  function restoreKeyboardLayout() {
    if (!root || root.hidden || !keyboardLayoutWasUndone()) {
      return;
    }
    if (restoredThisFrame) {
      if (!restoreDeferred) {
        restoreDeferred = true;
        global.requestAnimationFrame(() => {
          restoreDeferred = false;
          restoreKeyboardLayout();
        });
      }
      return;
    }
    restoredThisFrame = true;
    global.requestAnimationFrame(() => {
      restoredThisFrame = false;
    });
    // The redraw took this keyboard's `transition: none` away along with
    // the lift and the room, so the kiosk's 150ms transition is now gliding
    // the dialog back down. Measured mid-glide, the field still looked clear
    // of the keys, nothing was re-lifted, and it slid in under them. Snap
    // both boxes to where they are headed before anything is measured; the
    // releases in settleKeyboardToActiveField put the original values back.
    [liftedFixedAncestor, reservedScroller].forEach((node) => {
      if (node && node.isConnected) {
        node.style.setProperty("transition", "none", "important");
      }
    });
    if (!activeTarget.isConnected) {
      // The redraw rebuilt the field from the same template, so it carries
      // the same id; carry on in that one.
      const replacement = activeTarget.id ? document.getElementById(activeTarget.id) : null;
      if (!isEligibleField(replacement)) {
        hideKeyboard();
        return;
      }
      swappedFromType = null;
      activeTarget = null;
      setActiveTarget(replacement);
      if (document.activeElement !== replacement) {
        replacement.focus({ preventScroll: true });
      }
    } else if (swappedFromType) {
      activeTarget.setAttribute("type", "text");
    }
    settleKeyboardToActiveField();
  }

  function watchKeyboardLayout() {
    if (layoutObserver || typeof global.MutationObserver !== "function") {
      return;
    }
    layoutObserver = new global.MutationObserver(restoreKeyboardLayout);
    layoutObserver.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["style", "type", ROOM_ATTRIBUTE],
    });
  }

  function stopWatchingKeyboardLayout() {
    if (layoutObserver) {
      layoutObserver.disconnect();
      layoutObserver = null;
    }
  }

  function showKeyboard() {
    if (!root) {
      root = buildRoot();
    }
    renderKeys();
    root.hidden = false;
    document.body.classList.add("icucrops-tk-open");
    watchKeyboardLayout();
    syncKeyboardToActiveField();
  }

  function hideKeyboard() {
    stopKeyRepeat();
    stopWatchingKeyboardLayout();
    releaseReservedRoom();
    if (root) {
      root.hidden = true;
    }
    document.body.classList.remove("icucrops-tk-open");
    setActiveTarget(null);
    shiftOn = false;
    symbolsOn = false;
  }

  function toggleKeyboardFor(target) {
    if (activeTarget === target && root && !root.hidden) {
      hideKeyboard();
      return;
    }
    setActiveTarget(target);
    target.focus({ preventScroll: false });
    showKeyboard();
  }

  function handleDoubleClick(event) {
    const target = event.target;
    if (!isEligibleField(target)) {
      return;
    }
    event.preventDefault();
    toggleKeyboardFor(target);
  }

  function handleDocumentPointerDown(event) {
    const target = event.target;
    if (target instanceof HTMLElement && target.closest("#icucrops-touch-keyboard")) {
      return;
    }
    if (isEligibleField(target)) {
      // Switching fields while the keyboard is already open should follow
      // the new field, not require a second double-tap.
      if (root && !root.hidden && activeTarget && activeTarget !== target) {
        setActiveTarget(target);
        renderKeys();
        syncKeyboardToActiveField();
      }
      return;
    }
    if (root && !root.hidden) {
      hideKeyboard();
    }
  }

  // The OTP pages move focus themselves: each digit focuses the next box, and
  // an emptied box focuses the one before it. The keyboard only ever followed
  // a finger (pointerdown above), so it kept typing into the box it was
  // opened on -- every digit after the first overwrote the second box, and
  // the code could never be finished on the panel. Following focus, not just
  // taps, keeps the keys on whichever field the page has moved on to.
  function handleDocumentFocusIn(event) {
    const target = event.target;
    if (!root || root.hidden || !activeTarget || activeTarget === target) {
      return;
    }
    if (!isEligibleField(target)) {
      return;
    }
    const wasNumericOnly = numericOnly;
    setActiveTarget(target);
    if (numericOnly !== wasNumericOnly) {
      renderKeys();
    }
    syncKeyboardToActiveField();
  }

  // A shared kiosk terminal has no business offering to copy one account's
  // typed credentials for the next person, or pasting whatever was last
  // copied on the panel into someone else's field. user-select: none (in
  // icucrops-touch-keyboard.css) already stops a long-press from creating a
  // selection to copy, but Chromium's paste bubble doesn't need a selection
  // to appear on an editable field, so it is blocked directly here too.
  function blockClipboardEvent(event) {
    const target = event.target;
    if (isEligibleField(target)) {
      event.preventDefault();
    }
  }

  // Blocking the clipboard events was never going to reach the Cut/Copy bar a
  // long press raises: that bar and the two drag handles are Chromium's own
  // touch selection UI, drawn by the browser rather than the page, so there is
  // no page event to cancel. What it does need is a *range* to act on -- it
  // has nothing to cut or copy without one -- so a range made on a kiosk field
  // is collapsed straight back to a caret and the bar dismisses itself.
  //
  // Declaring the fields unselectable would also stop it, and is what the
  // stylesheet used to do, but that took tap-to-place-caret with it: on a
  // touch panel moving the caret is the same selection machinery, and every
  // character ended up at the end of the field. Collapsing leaves the caret
  // exactly where the finger put it.
  function collapseSelectionIn(element) {
    if (!(element instanceof HTMLElement) || !isEligibleField(element)) {
      return;
    }
    if (!supportsSelectionRange(element)) {
      return;
    }
    let start = null;
    let end = null;
    try {
      start = element.selectionStart;
      end = element.selectionEnd;
    } catch {
      return;
    }
    if (start === null || end === null || start === end) {
      return;
    }
    try {
      // Collapsed to the end of what was selected, which is where a caret
      // lands after a word is picked out on a normal keyboard.
      element.setSelectionRange(end, end);
    } catch {
      /* the field refused a caret; nothing further to do */
    }
  }

  function handleFieldSelect(event) {
    collapseSelectionIn(event.target);
  }

  function handleDocumentSelectionChange() {
    // selectionchange is fired at the document, so the field has to come from
    // whatever currently holds focus.
    collapseSelectionIn(document.activeElement);
  }

  // Injected rather than left to icucrops-touch-keyboard.css, so every page
  // that runs this script gets it without a stylesheet of its own to keep in
  // step. The ::after is the last item of whatever layout the scroller uses --
  // block, flex or grid -- so it always extends the scroll range.
  function installRoomStyle() {
    if (document.getElementById("icucrops-tk-room-style")) {
      return;
    }
    const style = document.createElement("style");
    style.id = "icucrops-tk-room-style";
    style.textContent = `[${ROOM_ATTRIBUTE}]::after {
  content: "" !important;
  display: block !important;
  height: var(${ROOM_HEIGHT_PROPERTY}, 0px) !important;
  min-height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  border: 0 !important;
  flex: none !important;
  grid-column: 1 / -1 !important;
  pointer-events: none !important;
  transition: none !important;
}`;
    (document.head || document.documentElement).appendChild(style);
  }

  function install() {
    if (global.ICuCropsTouchKeyboard?.installed) {
      return;
    }
    installRoomStyle();
    document.addEventListener("dblclick", handleDoubleClick, true);
    document.addEventListener("pointerdown", handleDocumentPointerDown, true);
    document.addEventListener("focusin", handleDocumentFocusIn, true);
    // A held key is released wherever the finger happens to be, which is
    // often no longer over the button, so the end of the hold is watched on
    // the document rather than on the button. touchend/touchcancel are
    // listened too, as a fallback for this touchscreen's driver occasionally
    // not delivering a matching pointerup/pointercancel -- without it, a
    // missed release leaves the repeat interval running and silently eating
    // every keypress typed after it.
    document.addEventListener("pointerup", stopKeyRepeat, true);
    document.addEventListener("pointercancel", stopKeyRepeat, true);
    document.addEventListener("touchend", stopKeyRepeat, true);
    document.addEventListener("touchcancel", stopKeyRepeat, true);
    document.addEventListener("copy", blockClipboardEvent, true);
    document.addEventListener("cut", blockClipboardEvent, true);
    document.addEventListener("paste", blockClipboardEvent, true);
    document.addEventListener("contextmenu", blockClipboardEvent, true);
    document.addEventListener("select", handleFieldSelect, true);
    document.addEventListener("selectionchange", handleDocumentSelectionChange, true);
    global.ICuCropsTouchKeyboard = {
      installed: true,
      hide: hideKeyboard,
    };
  }

  if (global.ICuCropsTouchKeyboard) {
    global.ICuCropsTouchKeyboard.install = install;
  } else {
    global.ICuCropsTouchKeyboard = { installed: false, install };
  }

  // On the shared app pages this only activates in Pi kiosk mode, set by
  // pi-runtime.js before this script runs. The standalone Wi-Fi onboarding
  // page has no such flag -- it is Pi-only by construction -- and calls
  // install() directly instead.
  if (global.ICuCropsPiMode === true) {
    install();
  }
})(window);
