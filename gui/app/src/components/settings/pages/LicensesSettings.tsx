import { useState } from 'react';
import { useLocalization } from '@fluent/react';
import { Typography } from '@/components/commons/Typography';
import {
  SettingsPageLayout,
  SettingsPagePaneLayout,
} from '@/components/settings/SettingsPageLayout';
import { FileIcon } from '@/components/commons/icon/FileIcon';
import noticeText from '@repo/NOTICE?raw';
import apacheLicenseText from '@repo/LICENSE?raw';
import mitLicenseText from '@repo/docs/licenses/LICENSE-MIT?raw';
import thirdPartyNoticesText from '@repo/server/core/resources/ThirdPartyNotices.txt?raw';
import lexendLicenseText from '@repo/gui/app/public/fonts/OFL-Lexend.txt?raw';
import notoSansLicenseText from '@repo/gui/app/public/fonts/OFL-NotoSans.txt?raw';
import openDyslexicLicenseText from '@repo/gui/app/public/fonts/OFL-OpenDyslexic.txt?raw';
import ubuntuLicenseText from '@repo/gui/app/public/fonts/UFL-Ubuntu.txt?raw';

interface LicenseEntry {
  id: string;
  titleKey: string;
  subtitleKey: string;
  text: string;
  defaultOpen?: boolean;
}

const LICENSE_ENTRIES: LicenseEntry[] = [
  {
    id: 'notice',
    titleKey: 'settings-licenses-notice-title',
    subtitleKey: 'settings-licenses-notice-subtitle',
    text: noticeText,
    defaultOpen: true,
  },
  {
    id: 'apache',
    titleKey: 'settings-licenses-apache-title',
    subtitleKey: 'settings-licenses-apache-subtitle',
    text: apacheLicenseText,
  },
  {
    id: 'mit',
    titleKey: 'settings-licenses-mit-title',
    subtitleKey: 'settings-licenses-mit-subtitle',
    text: mitLicenseText,
  },
  {
    id: 'third-party',
    titleKey: 'settings-licenses-third_party-title',
    subtitleKey: 'settings-licenses-third_party-subtitle',
    text: thirdPartyNoticesText,
  },
  {
    id: 'font-lexend',
    titleKey: 'settings-licenses-font_lexend-title',
    subtitleKey: 'settings-licenses-font_ofl-subtitle',
    text: lexendLicenseText,
  },
  {
    id: 'font-noto-sans',
    titleKey: 'settings-licenses-font_noto_sans-title',
    subtitleKey: 'settings-licenses-font_ofl-subtitle',
    text: notoSansLicenseText,
  },
  {
    id: 'font-opendyslexic',
    titleKey: 'settings-licenses-font_opendyslexic-title',
    subtitleKey: 'settings-licenses-font_ofl-subtitle',
    text: openDyslexicLicenseText,
  },
  {
    id: 'font-ubuntu',
    titleKey: 'settings-licenses-font_ubuntu-title',
    subtitleKey: 'settings-licenses-font_ufl-subtitle',
    text: ubuntuLicenseText,
  },
];

export function LicensesSettings() {
  const { l10n } = useLocalization();
  const [bundledNotices, setBundledNotices] = useState<string | null>(null);

  const loadBundledNotices = () => {
    if (bundledNotices !== null) return;
    setBundledNotices('Loading...');
    fetch('/licenses/THIRD-PARTY-NOTICES.txt')
      .then((res) => (res.ok ? res.text() : Promise.reject(res.status)))
      .then((text) => setBundledNotices(text))
      .catch(() =>
        setBundledNotices(
          'Unable to load bundled third-party notices. See licenses/THIRD-PARTY-NOTICES.txt in the application bundle.'
        )
      );
  };

  return (
    <SettingsPageLayout>
      <SettingsPagePaneLayout icon={<FileIcon />} id="licenses">
        <>
          <Typography variant="main-title">
            {l10n.getString('settings-licenses')}
          </Typography>
          <Typography color="secondary">
            {l10n.getString('settings-licenses-description')}
          </Typography>
          <div className="flex flex-col gap-3 mt-2">
            {LICENSE_ENTRIES.map((entry) => (
              <details
                key={entry.id}
                open={entry.defaultOpen}
                className="rounded-lg border border-background-50 bg-background-70 overflow-hidden"
              >
                <summary className="cursor-pointer select-none px-4 py-3 flex flex-col gap-0.5 hover:bg-background-60/50 transition-colors">
                  <Typography variant="section-title">
                    {l10n.getString(entry.titleKey)}
                  </Typography>
                  <Typography variant="vr-accessible" color="secondary">
                    {l10n.getString(entry.subtitleKey)}
                  </Typography>
                </summary>
                <pre className="px-4 py-3 border-t border-background-50 text-xs font-mono text-background-20 whitespace-pre-wrap break-words max-h-96 overflow-y-auto select-text">
                  {entry.text}
                </pre>
              </details>
            ))}
            <details
              onToggle={(e) => {
                if (e.currentTarget.open) loadBundledNotices();
              }}
              className="rounded-lg border border-background-50 bg-background-70 overflow-hidden"
            >
              <summary className="cursor-pointer select-none px-4 py-3 flex flex-col gap-0.5 hover:bg-background-60/50 transition-colors">
                <Typography variant="section-title">
                  {l10n.getString('settings-licenses-bundled-title')}
                </Typography>
                <Typography variant="vr-accessible" color="secondary">
                  {l10n.getString('settings-licenses-bundled-subtitle')}
                </Typography>
              </summary>
              <pre className="px-4 py-3 border-t border-background-50 text-xs font-mono text-background-20 whitespace-pre-wrap break-words max-h-96 overflow-y-auto select-text">
                {bundledNotices ?? ''}
              </pre>
            </details>
          </div>
        </>
      </SettingsPagePaneLayout>
    </SettingsPageLayout>
  );
}
