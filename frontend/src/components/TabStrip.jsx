function tabLabel(tab) {
  if (tab.kind === 'list') return 'Claims';
  if (tab.kind === 'new-claim') return 'New Claim';
  if (tab.kind === 'agent') return 'Agent';
  return `Claim ${tab.claimId.slice(0, 8)}`;
}

export default function TabStrip({ tabs, activeTabId, onSelect, onClose }) {
  return (
    <div className="tab-strip">
      {tabs.map((tab) => (
        <div
          key={tab.id}
          className={`tab-strip-item ${tab.id === activeTabId ? 'tab-strip-active' : ''}`}
          onClick={() => onSelect(tab.id)}
        >
          <span className="tab-strip-label">{tabLabel(tab)}</span>
          {tab.kind !== 'list' && (
            <button
              type="button"
              className="tab-strip-close"
              onClick={(e) => {
                e.stopPropagation();
                onClose(tab.id);
              }}
              aria-label="Close tab"
            >
              ×
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
