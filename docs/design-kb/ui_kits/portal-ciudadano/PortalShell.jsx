// Portal Ciudadano shell: white header (logo + contact), navy footer, chat FAB.
(function () {
  const DS = window.ChacoNODODesignSystem_dc2a68;

  function Header({ authed, onHome, onLogin, onLogout }) {
    const P = window.PORTAL;
    return (
      <header style={{ background: 'var(--bg-white)', borderBottom: '1px solid var(--border-base)', position: 'sticky', top: 0, zIndex: 30, boxShadow: 'var(--shadow-xs)' }}>
        <div style={{ maxWidth: 1120, margin: '0 auto', padding: '12px 24px', display: 'flex', alignItems: 'center', gap: 16 }}>
          <img src="../../assets/logo-chaco-horizontal.png" alt="Gobierno del Chaco" style={{ height: 38, cursor: 'pointer' }} onClick={onHome} />
          <div style={{ flex: 1 }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }} className="contact">
            <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-heading)', fontWeight: 600 }}>
              <span style={{ width: 30, height: 30, borderRadius: 'var(--radius-lg)', background: 'var(--bg-brand-soft)', color: 'var(--text-fg-brand)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13 }}><i className="fas fa-phone" /></span>
              {P.contact.phone}
            </span>
            {authed
              ? <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <DS.Avatar name={P.ciudadano.name} size={34} />
                  <DS.Button size="sm" variant="secondary" icon="fas fa-right-from-bracket" onClick={onLogout}>Salir</DS.Button>
                </div>
              : <DS.Button size="sm" variant="brand" icon="fas fa-right-to-bracket" onClick={onLogin}>Ingresar</DS.Button>}
          </div>
        </div>
      </header>
    );
  }

  function Footer() {
    const P = window.PORTAL;
    return (
      <footer style={{ background: 'var(--bg-navy)', color: '#fff', marginTop: 56 }}>
        <div style={{ maxWidth: 1120, margin: '0 auto', padding: '44px 24px 28px', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 32 }}>
          <div>
            <img src="../../assets/logo-chaco-horizontal.png" alt="Gobierno del Chaco" style={{ height: 34, filter: 'brightness(0) invert(1)', marginBottom: 12 }} />
            <p style={{ color: '#cbd5e1', fontSize: 13, lineHeight: 1.6, margin: 0, maxWidth: 280 }}>
              Portal de programas y trámites sociales del Gobierno de la Provincia del Chaco.
            </p>
          </div>
          <div>
            <h4 style={{ color: '#fff', fontSize: 15, margin: '0 0 12px' }}>Contacto</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13, color: '#cbd5e1' }}>
              <span><i className="fas fa-phone" style={{ width: 18 }} /> {P.contact.phone}</span>
              <span><i className="fas fa-envelope" style={{ width: 18 }} /> {P.contact.email}</span>
            </div>
          </div>
          <div>
            <h4 style={{ color: '#fff', fontSize: 15, margin: '0 0 12px' }}>Horarios de atención</h4>
            <p style={{ color: '#cbd5e1', fontSize: 13, margin: 0, lineHeight: 1.6 }}>Lunes a Viernes<br />9:00 — 17:00 hs</p>
          </div>
        </div>
        <div style={{ borderTop: '1px solid rgba(255,255,255,.12)', padding: '16px 24px', textAlign: 'center' }}>
          <span style={{ color: '#94a3b8', fontSize: 12.5 }}>© 2026 Gobierno del Chaco · Plataforma NODO — Todos los derechos reservados</span>
        </div>
      </footer>
    );
  }

  function ChatFab() {
    const [open, setOpen] = React.useState(false);
    return (
      <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 40 }}>
        {open && (
          <div style={{ position: 'absolute', bottom: 70, right: 0, width: 300, background: 'var(--bg-white)', borderRadius: 'var(--radius-xl)', boxShadow: 'var(--shadow-xl)', border: '1px solid var(--border-base)', overflow: 'hidden' }}>
            <div style={{ background: 'var(--gradient-brand)', color: '#fff', padding: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#fff' }} />
              <strong style={{ fontSize: 14 }}>Mesa de Ayuda</strong>
            </div>
            <div style={{ padding: 22, textAlign: 'center', color: 'var(--text-body-subtle)' }}>
              <i className="fas fa-headset" style={{ fontSize: 30, color: 'var(--text-fg-brand)', marginBottom: 10, display: 'block' }} />
              <div style={{ fontWeight: 700, color: 'var(--text-heading)', marginBottom: 2 }}>Asistencia técnica</div>
              <div style={{ fontSize: 13 }}>Lun a Vie, 9 a 17 hs</div>
            </div>
          </div>
        )}
        <button onClick={() => setOpen((o) => !o)} aria-label="Ayuda" style={{ width: 56, height: 56, borderRadius: '50%', border: 'none', cursor: 'pointer', background: 'var(--gradient-brand)', color: '#fff', fontSize: 20, boxShadow: 'var(--shadow-lg)' }}>
          <i className={open ? 'fas fa-xmark' : 'fas fa-comments'} />
        </button>
      </div>
    );
  }

  Object.assign(window, { PortalHeader: Header, PortalFooter: Footer, ChatFab });
})();
