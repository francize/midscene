#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import archiver from 'archiver';

/**
 * Chrome 扩展打包脚本
 * 将构建好的扩展文件打包为 .zip 文件，便于上传到 Chrome Web Store
 */

// 获取当前文件的目录路径
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 读取 package.json 获取版本号
const packageJsonPath = path.resolve(__dirname, '../package.json');
const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));

// 验证版本号格式，防止注入攻击
const version = packageJson.version;
if (!/^[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.]+)?$/.test(version)) {
  console.error('Invalid version format in package.json');
  process.exit(1);
}

// 创建扩展输出目录
const extensionDir = path.resolve(__dirname, '../extension_output');
if (!fs.existsSync(extensionDir)) {
  fs.mkdirSync(extensionDir, {
    recursive: true,
  });
}

// 源目录 - dist (构建输出)
const distDir = path.resolve(__dirname, '../dist');

// 创建 zip 文件名，包含版本号
const zipFileName = `midscene-extension-v${version}.zip`;
const zipFilePath = path.resolve(extensionDir, zipFileName);

// 删除已存在的 zip 文件
if (fs.existsSync(zipFilePath)) {
  fs.unlinkSync(zipFilePath);
}

// 创建文件流以写入压缩数据
const output = fs.createWriteStream(zipFilePath);
const archive = archiver('zip', {
  zlib: {
    level: 9,
  }, // 设置最高压缩级别
});

// 监听所有压缩数据写入完成事件
output.on('close', () => {
  console.log(
    `Extension packed successfully: ${zipFileName} (${archive.pointer()} total bytes saved in extension directory)`,
  );
});

// 处理警告和错误
archive.on('warning', (err) => {
  if (err.code === 'ENOENT') {
    console.warn('Warning during archiving:', err);
  } else {
    console.error('Error during archiving:', err);
    process.exit(1);
  }
});

archive.on('error', (err) => {
  console.error('Error during archiving:', err);
  process.exit(1);
});

// 将压缩数据导出到文件
archive.pipe(output);

// 将 dist 目录中的文件添加到压缩包，放置在根目录下
archive.directory(distDir, false);

// 完成压缩操作（注意：此时数据流还没有完全完成）
archive.finalize();
