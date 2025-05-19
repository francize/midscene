/**
 * Midscene 水流动画控制器
 * 提供可视化反馈，在浏览器自动化过程中展示水流边框动画和鼠标指针动作
 */
const midsceneWaterFlowAnimation = {
  /** 样式元素引用 */
  styleElement: null as null | HTMLStyleElement,

  /** 鼠标指针元素的数据属性名 */
  mousePointerAttribute: 'data-water-flow-pointer',

  /** 最后一次调用时间戳 */
  lastCallTime: 0,

  /** 自动清理定时器 */
  cleanupTimeout: null as null | number,

  /**
   * 注册自清理定时器
   * 如果在指定时间内没有新的调用，将自动清理所有动画元素
   */
  registerSelfCleaning() {
    // 如果 30 秒内没有调用，清理所有指示器
    this.lastCallTime = Date.now();
    const cleaningTimeout = 30000;

    if (this.cleanupTimeout) {
      clearTimeout(this.cleanupTimeout);
    }

    this.cleanupTimeout = window.setTimeout(() => {
      const now = Date.now();
      if (now - this.lastCallTime >= cleaningTimeout) {
        this.disable();
      }
    }, cleaningTimeout);
  },

  /**
   * 显示鼠标指针
   * 在指定位置创建一个鼠标指针动画元素，显示点击或交互位置
   * 
   * @param x 鼠标指针 X 坐标
   * @param y 鼠标指针 Y 坐标
   */
  showMousePointer(x: number, y: number) {
    this.enable(); // 显示水流动画
    this.registerSelfCleaning();
    const existingPointer = document.querySelector(
      `div[${this.mousePointerAttribute}]`,
    ) as HTMLDivElement | null;

    // 清除任何现有的超时以防止竞态条件
    if (existingPointer) {
      const timeoutId = Number(existingPointer.getAttribute('data-timeout-id'));
      if (timeoutId) clearTimeout(timeoutId);
      const removeTimeoutId = Number(
        existingPointer.getAttribute('data-remove-timeout-id'),
      );
      if (removeTimeoutId) clearTimeout(removeTimeoutId);
    }

    // 指针大小
    const size = 30;
    
    // 使用现有指针或创建新指针
    const pointer =
      existingPointer ||
      (() => {
        const p = document.createElement('div');
        p.setAttribute(this.mousePointerAttribute, 'true');
        p.style.position = 'fixed';
        p.style.width = `${size}px`;
        p.style.height = `${size}px`;
        p.style.borderRadius = '50%';
        p.style.backgroundColor = 'rgba(0, 0, 255, 0.3)';
        p.style.border = '1px solid rgba(0, 0, 255, 0.3)';
        p.style.zIndex = '99999';
        p.style.transition = 'all 1s ease-in';
        p.style.pointerEvents = 'none'; // 使指针不可点击
        // 如果是新指针，从偏移位置开始
        p.style.left = `${x - size / 2}px`;
        p.style.top = `${y - size / 2}px`;
        document.body.appendChild(p);
        return p;
      })();

    // 使用 requestAnimationFrame 确保平滑移动
    requestAnimationFrame(() => {
      pointer.style.left = `${x - size / 2}px`;
      pointer.style.top = `${y - size / 2}px`;
      pointer.style.opacity = '1';
    });

    // 设置新的超时：3秒后淡出，再延迟500ms移除
    const fadeTimeoutId = setTimeout(() => {
      pointer.style.opacity = '0';
      const removeTimeoutId = setTimeout(() => {
        if (pointer.parentNode) {
          document.body.removeChild(pointer);
        }
      }, 500);
      pointer.setAttribute('data-remove-timeout-id', String(removeTimeoutId));
    }, 3000);
    pointer.setAttribute('data-timeout-id', String(fadeTimeoutId));
  },

  /**
   * 隐藏鼠标指针
   * 移除当前显示的鼠标指针元素
   */
  hideMousePointer() {
    this.registerSelfCleaning();
    const pointer = document.querySelector(
      `div[${this.mousePointerAttribute}]`,
    ) as HTMLDivElement | null;
    if (pointer) {
      document.body.removeChild(pointer);
    }
  },

  /**
   * 启用水流动画
   * 创建并插入样式元素，在页面边缘添加水流动画效果
   */
  enable() {
    this.registerSelfCleaning();
    if (this.styleElement) {
      // 检查样式元素是否仍在DOM树中
      if (document.head.contains(this.styleElement)) {
        return;
      }
      this.styleElement = null;
    }

    // 创建样式元素并定义水流动画CSS
    this.styleElement = document.createElement('style');
    this.styleElement.id = 'water-flow-animation';
    this.styleElement.textContent = `
    html::before {
      content: "";
      position: fixed;
      top: 0; right: 0; bottom: 0; left: 0;
      pointer-events: none;
      z-index: 9999;
      background:
        linear-gradient(to right, rgba(30, 144, 255, 0.4), transparent 50%) left,
        linear-gradient(to left, rgba(30, 144, 255, 0.4), transparent 50%) right,
        linear-gradient(to bottom, rgba(30, 144, 255, 0.4), transparent 50%) top,
        linear-gradient(to top, rgba(30, 144, 255, 0.4), transparent 50%) bottom;
      background-repeat: no-repeat;
      background-size: 10% 100%, 10% 100%, 100% 10%, 100% 10%;
      animation: waterflow 5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
      filter: blur(8px);
    }

    @keyframes waterflow {
      0%, 100% {
        background-image:
          linear-gradient(to right, rgba(30, 144, 255, 0.4), transparent 50%),
          linear-gradient(to left, rgba(30, 144, 255, 0.4), transparent 50%),
          linear-gradient(to bottom, rgba(30, 144, 255, 0.4), transparent 50%),
          linear-gradient(to top, rgba(30, 144, 255, 0.4), transparent 50%);
        transform: scale(1);
      }
      25% {
        background-image:
          linear-gradient(to right, rgba(30, 144, 255, 0.39), transparent 52%),
          linear-gradient(to left, rgba(30, 144, 255, 0.39), transparent 52%),
          linear-gradient(to bottom, rgba(30, 144, 255, 0.39), transparent 52%),
          linear-gradient(to top, rgba(30, 144, 255, 0.39), transparent 52%);
        transform: scale(1.03);
      }
      50% {
        background-image:
          linear-gradient(to right, rgba(30, 144, 255, 0.38), transparent 55%),
          linear-gradient(to left, rgba(30, 144, 255, 0.38), transparent 55%),
          linear-gradient(to bottom, rgba(30, 144, 255, 0.38), transparent 55%),
          linear-gradient(to top, rgba(30, 144, 255, 0.38), transparent 55%);
        transform: scale(1.05);
      }
      75% {
        background-image:
          linear-gradient(to right, rgba(30, 144, 255, 0.39), transparent 52%),
          linear-gradient(to left, rgba(30, 144, 255, 0.39), transparent 52%),
          linear-gradient(to bottom, rgba(30, 144, 255, 0.39), transparent 52%),
          linear-gradient(to top, rgba(30, 144, 255, 0.39), transparent 52%);
        transform: scale(1.03);
      }
    }
    `;
    document.head.appendChild(this.styleElement);
  },

  /**
   * 禁用水流动画
   * 移除所有动画相关的元素和样式
   */
  disable() {
    if (this.cleanupTimeout) {
      clearTimeout(this.cleanupTimeout);
      this.cleanupTimeout = null;
    }

    // 移除所有水流动画样式元素
    const styleElements = document.querySelectorAll('#water-flow-animation');
    styleElements.forEach((element) => {
      document.head.removeChild(element);
    });
    this.styleElement = null;

    // 移除所有鼠标指针元素
    const mousePointers = document.querySelectorAll(
      `div[${this.mousePointerAttribute}]`,
    );
    mousePointers.forEach((element) => {
      document.body.removeChild(element);
    });
  },
};

export {};

/**
 * 扩展 Window 接口，添加 midsceneWaterFlowAnimation 属性
 */
declare global {
  interface Window {
    midsceneWaterFlowAnimation: typeof midsceneWaterFlowAnimation;
  }
}

// 确保 midsceneWaterFlowAnimation 实例在全局范围内可访问
(window as any).midsceneWaterFlowAnimation =
  (window as any).midsceneWaterFlowAnimation || midsceneWaterFlowAnimation;

// 初始启用水流动画
(window as any).midsceneWaterFlowAnimation.enable();
