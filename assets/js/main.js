(() => {
  const header = document.querySelector('[data-header]');
  const menuToggle = document.querySelector('[data-menu-toggle]');
  const menu = document.querySelector('[data-menu]');

  const setHeaderState = () => {
    if (!header) return;
    header.classList.toggle('is-scrolled', window.scrollY > 96);
  };
  setHeaderState();
  window.addEventListener('scroll', setHeaderState, { passive: true });

  if (menuToggle && menu) {
    menuToggle.addEventListener('click', () => {
      const open = menuToggle.getAttribute('aria-expanded') !== 'true';
      menuToggle.setAttribute('aria-expanded', String(open));
      menu.classList.toggle('is-open', open);
      document.body.classList.toggle('menu-open', open);
    });
    menu.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => {
      menuToggle.setAttribute('aria-expanded', 'false');
      menu.classList.remove('is-open');
      document.body.classList.remove('menu-open');
    }));
  }

  const heroMedia = document.querySelector('[data-hero-media]');
  if (heroMedia && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    window.addEventListener('pointermove', (event) => {
      const x = (event.clientX / window.innerWidth - 0.5) * 10;
      const y = (event.clientY / window.innerHeight - 0.5) * 10;
      heroMedia.style.transform = `translate3d(${x}px, ${y}px, 0)`;
    }, { passive: true });
  }

  const directory = document.querySelector('[data-people-directory]');
  if (directory) {
    const buttons = directory.querySelectorAll('[data-role-filter]');
    const sections = directory.querySelectorAll('[data-role-section]');
    buttons.forEach((button) => button.addEventListener('click', () => {
      const selected = button.dataset.roleFilter;
      buttons.forEach((item) => item.classList.toggle('is-active', item === button));
      sections.forEach((section) => {
        section.hidden = selected !== 'all' && section.dataset.roleSection !== selected;
      });
    }));
  }

  const publications = document.querySelector('[data-publications]');
  if (publications) {
    const input = publications.querySelector('[data-publication-search]');
    const items = [...publications.querySelectorAll('.publication')];
    const count = publications.querySelector('[data-publication-count]');
    const empty = publications.querySelector('[data-publication-empty]');
    if (input && items.length) {
      input.addEventListener('input', () => {
        const query = input.value.trim().toLocaleLowerCase();
        let visible = 0;
        items.forEach((item) => {
          const matches = !query || item.textContent.toLocaleLowerCase().includes(query);
          item.hidden = !matches;
          if (matches) visible += 1;
        });
        count.textContent = `${visible} ${visible === 1 ? 'paper' : 'papers'}`;
        empty.hidden = visible !== 0;
      });
    }
  }

  document.querySelectorAll('[data-schedule-more]').forEach((scheduleMore) => {
    const controlledRows = document.getElementById(scheduleMore.getAttribute('aria-controls'));
    if (!controlledRows) return;
    const extraRows = [...controlledRows.querySelectorAll('[data-schedule-extra]')];
    const moreCount = Number(scheduleMore.dataset.moreCount || extraRows.length);
    const moreLabel = scheduleMore.dataset.moreLabel || 'more items';
    extraRows.forEach((row) => { row.hidden = true; });
    scheduleMore.hidden = false;
    scheduleMore.addEventListener('click', () => {
      const expanded = scheduleMore.getAttribute('aria-expanded') !== 'true';
      scheduleMore.setAttribute('aria-expanded', String(expanded));
      extraRows.forEach((row) => { row.hidden = !expanded; });
      scheduleMore.textContent = expanded ? 'Show fewer' : `See ${moreCount} ${moreLabel}`;
    });
  });
})();
