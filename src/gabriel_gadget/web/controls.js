// Shared styled form primitives. Native elements stay encapsulated here.
function wrapper(label, id) {
  const group = document.createElement('div'); group.className = 'field';
  const caption = document.createElement('label'); caption.htmlFor = id; caption.id = id + '-label'; caption.textContent = label;
  group.append(caption); return group;
}
export function inputField(label, id, type = 'text') {
  const group = wrapper(label, id), control = document.createElement('input');
  control.id = id; control.type = type; control.autocomplete = 'off';
  group.append(control); return { group, control };
}
export function textareaField(label, id) {
  const group = wrapper(label, id), control = document.createElement('textarea');
  control.id = id; control.rows = 3; group.append(control); return { group, control };
}
export function selectField(label, id, options) {
  const group = wrapper(label, id), control = document.createElement('button');
  control.id = id; control.type = 'button'; control.className = 'select-control';
  control.setAttribute('role', 'combobox'); control.setAttribute('aria-haspopup', 'listbox');
  control.setAttribute('aria-expanded', 'false'); control.setAttribute('aria-labelledby', id + '-label');
  control.setAttribute('aria-controls', id + '-options');
  const text = document.createElement('span'), arrow = document.createElement('span');
  arrow.textContent = '⌄'; arrow.setAttribute('aria-hidden', 'true'); control.append(text, arrow);
  const menu = document.createElement('div'); menu.id = id + '-options'; menu.className = 'select-menu';
  menu.setAttribute('role', 'listbox'); menu.setAttribute('aria-labelledby', id + '-label'); menu.hidden = true;
  group.append(control, menu); group.classList.add('select-field');
  let items = [], current = '', active = 0;
  function paint() {
    text.textContent = items.find(([value]) => value === current)?.[1] || 'Choose a persona';
    [...menu.children].forEach((item, index) => {
      item.setAttribute('aria-selected', String(items[index][0] === current));
      item.classList.toggle('highlighted', index === active);
    });
  }
  function open(value) {
    menu.hidden = !value; control.setAttribute('aria-expanded', String(value));
    if (value && items[active]) control.setAttribute('aria-activedescendant', id + '-option-' + active);
    else control.removeAttribute('aria-activedescendant');
  }
  function choose(index) {
    if (!items[index] || control.disabled) return;
    current = items[index][0]; active = index; paint(); open(false);
    control.dispatchEvent(new Event('change', { bubbles: true })); control.focus();
  }
  function setOptions(next) {
    items = next; menu.replaceChildren();
    if (!items.some(([value]) => value === current)) current = items[0]?.[0] || '';
    active = Math.max(0, items.findIndex(([value]) => value === current));
    items.forEach(([value, label], index) => {
      const item = document.createElement('button'); item.type = 'button'; item.className = 'select-option';
      item.id = id + '-option-' + index; item.setAttribute('role', 'option'); item.tabIndex = -1;
      item.textContent = label; item.onclick = () => choose(index); menu.append(item);
    });
    paint(); open(false);
  }
  Object.defineProperty(control, 'value', { get: () => current, set: value => {
    current = value; active = Math.max(0, items.findIndex(([item]) => item === value)); paint();
  }});
  control.onclick = () => { if (!control.disabled) { paint(); open(menu.hidden); } };
  control.onkeydown = event => {
    if (control.disabled || !items.length) return;
    if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      active = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 :
        (active + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      paint(); open(true); menu.children[active].scrollIntoView({ block: 'nearest' });
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault(); menu.hidden ? open(true) : choose(active);
    } else if (event.key === 'Escape') { event.preventDefault(); open(false); }
    else if (event.key === 'Tab') open(false);
  };
  document.addEventListener('pointerdown', event => { if (!group.contains(event.target)) open(false); });
  group.addEventListener('focusout', event => { if (!group.contains(event.relatedTarget)) open(false); });
  setOptions(options);
  return { group, control, setOptions };
}
