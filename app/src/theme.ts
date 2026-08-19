/**
 * 顾问账簿主题配置
 * Advisor's Ledger Theme
 *
 * 设计理念：以合同法律文档世界为视觉灵感
 * 深墨海军蓝(权威) + 羊皮纸(温度) + 古金(尊贵) + 深朱(警示)
 *
 * Hallmark · genre: editorial · designed-as-app
 * 令牌与 index.css :root 保持一一对应，禁止内联新色值
 */
import type { ThemeConfig } from 'antd'

/** 色彩令牌 */
export const palette = {
  ink: '#1B2332',           // 深墨海军蓝 — 侧边栏、标题
  inkLight: '#2A3548',      // 浅墨蓝 — 悬停态
  inkDeep: '#141B27',       // 至深墨 — 折叠触发条
  parchment: '#F6F3EC',    // 羊皮纸 — 全局背景
  parchmentDark: '#EDE8DC', // 深羊皮纸 — 次级背景
  parchmentLight: '#FAF7F0',// 浅羊皮纸 — 悬停浮层底
  gold: '#B8954A',          // 古金 — 强调色、激活态
  goldLight: '#D4B068',    // 浅金 — 悬停态
  goldDark: '#9A7A35',     // 深金 — 按下态
  goldFaint: '#C9AE72',    // 淡金 — 线脚、完成态
  slate: '#5A6B7F',         // 石板蓝灰 — 次级文字
  slateLight: '#8B9BAE',   // 浅石板 — 辅助文字
  porcelain: '#FFFFFF',     // 瓷白 — 卡片表面
  crimson: '#9B2C2C',       // 深朱 — 风险、危险
  sage: '#5B7553',          // 鼠尾草绿 — 成功、已确认
  amber: '#C4862B',         // 琥珀 — 警告、待确认
  // 线与底纹
  rule: '#E8E2D4',
  ruleStrong: '#D8D0C0',
  ruleGold: '#D8C9A5',
  rowHover: '#F3EEE3',
  // 侧边栏暗面
  siderText: '#96A0B3',
  siderTextDim: '#64708A',
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
    colorBgElevated: palette.porcelain,

    // 文字
    colorTextHeading: palette.ink,
    colorText: '#2C3E50',
    colorTextSecondary: palette.slate,
    colorTextTertiary: palette.slateLight,
    colorTextQuaternary: '#B0BCC8',

    // 边框
    colorBorder: palette.ruleStrong,
    colorBorderSecondary: palette.rule,

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
      // 暗面菜单：透明选中块 + CSS 金色游标（见 index.css）
      darkItemBg: 'transparent',
      darkItemSelectedBg: 'transparent',
      darkItemSelectedColor: palette.gold,
      darkItemHoverBg: 'rgba(184, 149, 74, 0.07)',
      darkItemHoverColor: palette.goldLight,
      darkItemColor: palette.siderText,
      itemBg: 'transparent',
      itemSelectedBg: 'transparent',
      itemSelectedColor: palette.gold,
      itemHoverBg: 'transparent',
      itemHoverColor: palette.goldLight,
      itemMarginInline: 0,
      itemBorderRadius: 0,
    },
    Card: {
      headerBg: 'transparent',
      headerFontSize: 15,
      paddingLG: 24,
    },
    Table: {
      headerBg: palette.parchmentDark,
      headerColor: palette.ink,
      headerSplitColor: 'transparent',
      rowHoverBg: palette.rowHover,
      borderColor: palette.rule,
    },
    Steps: {
      colorPrimary: palette.gold,
    },
    Button: {
      // 古金主按钮：暖墨薄影替代 antd 默认彩色投影
      primaryShadow: '0 1px 2px rgba(27, 35, 50, 0.14)',
      defaultShadow: 'none',
      fontWeight: 500,
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
      horizontalItemGutter: 28,
    },
    Drawer: {
      colorBgElevated: palette.porcelain,
    },
    Modal: {
      colorBgElevated: palette.porcelain,
    },
    Tooltip: {
      colorBgSpotlight: palette.ink,
    },
  },
}

/** CSS 自定义属性（与 index.css :root 一致） */
export const cssVars = `
  --ink: ${palette.ink};
  --ink-light: ${palette.inkLight};
  --ink-deep: ${palette.inkDeep};
  --parchment: ${palette.parchment};
  --parchment-dark: ${palette.parchmentDark};
  --parchment-light: ${palette.parchmentLight};
  --gold: ${palette.gold};
  --gold-light: ${palette.goldLight};
  --gold-dark: ${palette.goldDark};
  --gold-faint: ${palette.goldFaint};
  --slate: ${palette.slate};
  --slate-light: ${palette.slateLight};
  --porcelain: ${palette.porcelain};
  --crimson: ${palette.crimson};
  --sage: ${palette.sage};
  --amber: ${palette.amber};
  --rule: ${palette.rule};
  --rule-strong: ${palette.ruleStrong};
  --rule-gold: ${palette.ruleGold};
  --font-serif: ${fonts.serif};
  --font-sans: ${fonts.sans};
  --font-mono: ${fonts.mono};
` as const
