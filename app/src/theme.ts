/**
 * 顾问账簿主题配置
 * Advisor's Ledger Theme
 *
 * 设计理念：以合同法律文档世界为视觉灵感
 * 深墨海军蓝(权威) + 羊皮纸(温度) + 古金(尊贵) + 深朱(警示)
 */
import type { ThemeConfig } from 'antd'

/** 色彩令牌 */
export const palette = {
  ink: '#1B2332',           // 深墨海军蓝 — 侧边栏、标题
  inkLight: '#2A3548',      // 浅墨蓝 — 悬停态
  parchment: '#F6F3EC',    // 羊皮纸 — 全局背景
  parchmentDark: '#EDE8DC', // 深羊皮纸 — 次级背景
  gold: '#B8954A',          // 古金 — 强调色、激活态
  goldLight: '#D4B068',    // 浅金 — 悬停态
  goldDark: '#9A7A35',     // 深金 — 按下态
  slate: '#5A6B7F',         // 石板蓝灰 — 次级文字
  slateLight: '#8B9BAE',   // 浅石板 — 辅助文字
  porcelain: '#FFFFFF',     // 瓷白 — 卡片表面
  crimson: '#9B2C2C',       // 深朱 — 风险、危险
  sage: '#5B7553',          // 鼠尾草绿 — 成功、已确认
  amber: '#C4862B',         // 琥珀 — 警告、待确认
} as const

/** 字体令牌 */
export const fonts = {
  serif: "'Noto Serif SC', 'Source Han Serif SC', 'Songti SC', serif",
  sans: "'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif",
  mono: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
} as const

/** Ant Design 主题配置 */
export const antdTheme: ThemeConfig = {
  token: {
    colorPrimary: palette.gold,
    colorInfo: palette.gold,
    colorSuccess: palette.sage,
    colorWarning: palette.amber,
    colorError: palette.crimson,
    colorLink: palette.gold,

    borderRadius: 4,
    fontFamily: fonts.sans,

    colorBgLayout: palette.parchment,
    colorBgContainer: palette.porcelain,

    // 文字
    colorTextHeading: palette.ink,
    colorText: '#2C3E50',
    colorTextSecondary: palette.slate,
    colorTextTertiary: palette.slateLight,
    colorTextQuaternary: '#B0BCC8',

    // 边框
    colorBorder: '#D8D0C0',
    colorBorderSecondary: '#E8E2D4',

    // 字号
    fontSize: 14,
    fontSizeLG: 16,
    fontSizeXL: 20,
    fontSizeHeading1: 28,
    fontSizeHeading2: 24,
    fontSizeHeading3: 20,
    fontSizeHeading4: 18,
    fontSizeHeading5: 16,
  },
  components: {
    Layout: {
      siderBg: palette.ink,
      headerBg: palette.porcelain,
      bodyBg: palette.parchment,
    },
    Menu: {
      darkItemBg: palette.ink,
      darkItemSelectedBg: palette.inkLight,
      darkItemSelectedColor: palette.gold,
      darkItemHoverBg: palette.inkLight,
      darkItemColor: '#A0AEC0',
      itemBg: 'transparent',
      itemSelectedBg: 'transparent',
      itemSelectedColor: palette.gold,
      itemHoverBg: 'transparent',
      itemHoverColor: palette.goldLight,
    },
    Card: {
      headerBg: 'transparent',
      headerFontSize: 15,
      paddingLG: 24,
    },
    Table: {
      headerBg: palette.parchmentDark,
      headerColor: palette.ink,
      rowHoverBg: '#F0EBE0',
      borderColor: '#D8D0C0',
    },
    Steps: {
      colorPrimary: palette.gold,
    },
    Button: {
      primaryShadow: 'none',
      defaultShadow: 'none',
    },
    Tag: {
      defaultBg: palette.parchmentDark,
      defaultColor: palette.slate,
    },
    Tabs: {
      inkBarColor: palette.gold,
      itemSelectedColor: palette.ink,
      itemColor: palette.slate,
      itemHoverColor: palette.gold,
    },
  },
}

/** CSS 自定义属性（供 index.css 和组件使用） */
export const cssVars = `
  --ink: ${palette.ink};
  --ink-light: ${palette.inkLight};
  --parchment: ${palette.parchment};
  --parchment-dark: ${palette.parchmentDark};
  --gold: ${palette.gold};
  --gold-light: ${palette.goldLight};
  --gold-dark: ${palette.goldDark};
  --slate: ${palette.slate};
  --slate-light: ${palette.slateLight};
  --porcelain: ${palette.porcelain};
  --crimson: ${palette.crimson};
  --sage: ${palette.sage};
  --amber: ${palette.amber};
  --font-serif: ${fonts.serif};
  --font-sans: ${fonts.sans};
  --font-mono: ${fonts.mono};
` as const
