const root = document.documentElement;
const saved = localStorage.getItem('theme');
if (saved === 'dark') root.classList.add('dark');

function toggleTheme() {
  root.classList.toggle('dark');
  localStorage.setItem('theme', root.classList.contains('dark') ? 'dark' : 'light');
}

document.querySelectorAll('#themeToggle,#themeToggleLarge').forEach((button) => button && button.addEventListener('click', toggleTheme));

const menu = document.getElementById('menuBtn');
const side = document.getElementById('sidebar');
if (menu && side) menu.addEventListener('click', () => side.classList.toggle('-translate-x-full'));

function showLoader() {
  const loader = document.getElementById('loader');
  if (loader) {
    loader.classList.remove('hidden');
    loader.classList.add('grid');
  }
}
window.showLoader = showLoader;
document.querySelectorAll('a[href="/dashboard"]').forEach((anchor) => anchor.addEventListener('click', showLoader));
setTimeout(() => document.querySelectorAll('.toast').forEach((toast) => toast.remove()), 4200);

function toast(message) {
  const item = document.createElement('div');
  item.className = 'toast success';
  item.textContent = message;
  const stack = document.createElement('div');
  stack.className = 'fixed right-4 top-4 z-50 space-y-2';
  stack.appendChild(item);
  document.body.appendChild(stack);
  setTimeout(() => stack.remove(), 5000);
}

async function requestReminderPermission() {
  if (!('Notification' in window)) {
    toast('This browser does not support desktop notifications.');
    return;
  }
  const permission = await Notification.requestPermission();
  toast(permission === 'granted' ? 'Medication reminders are enabled.' : 'Notifications were not enabled.');
}

document.getElementById('enableNotifications')?.addEventListener('click', requestReminderPermission);

const notifiedDoseIds = new Set(JSON.parse(sessionStorage.getItem('notifiedDoseIds') || '[]'));
function rememberNotification(id) {
  notifiedDoseIds.add(id);
  sessionStorage.setItem('notifiedDoseIds', JSON.stringify([...notifiedDoseIds]));
}

async function pollReminders() {
  if (!document.querySelector('[data-dose-id]')) return;
  try {
    const response = await fetch('/api/reminders');
    const data = await response.json();
    data.reminders.filter((reminder) => reminder.should_notify && !notifiedDoseIds.has(reminder.id)).forEach((reminder) => {
      const title = reminder.status === 'Due Now' ? 'Dose due now' : 'Upcoming medication';
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, { body: reminder.message, tag: `dose-${reminder.id}` });
      } else {
        toast(reminder.message);
      }
      rememberNotification(reminder.id);
    });
  } catch (error) {
    console.warn('Unable to check reminders', error);
  }
}

pollReminders();
setInterval(pollReminders, 60000);

async function charts() {
  if (!window.MediTrackCharts) return;
  const response = await fetch('/api/statistics');
  const data = await response.json();
  const green = '#059669', blue = '#2563eb', red = '#e11d48', grid = 'rgba(148,163,184,.22)';
  new Chart(document.getElementById('weeklyChart'), {
    type: 'line',
    data: { labels: data.weekly.map((x) => x.label), datasets: [{ label: 'Adherence %', data: data.weekly.map((x) => x.value), borderColor: green, backgroundColor: 'rgba(5,150,105,.12)', fill: true, tension: .35 }] },
    options: { scales: { y: { min: 0, max: 100, grid: { color: grid } }, x: { grid: { display: false } } } },
  });
  new Chart(document.getElementById('monthlyChart'), {
    type: 'bar',
    data: { labels: data.monthly.map((x) => x.label), datasets: [{ label: 'Adherence %', data: data.monthly.map((x) => x.value), backgroundColor: blue, borderRadius: 8 }] },
    options: { scales: { y: { min: 0, max: 100, grid: { color: grid } }, x: { grid: { display: false } } } },
  });
  new Chart(document.getElementById('donutChart'), { type: 'doughnut', data: { labels: ['Taken', 'Missed'], datasets: [{ data: [data.taken, data.missed], backgroundColor: [green, red], borderWidth: 0 }] }, options: { cutout: '68%' } });
  document.getElementById('completion').textContent = `${data.completion}%`;
}
charts();
