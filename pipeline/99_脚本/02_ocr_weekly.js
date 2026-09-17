// 对《测绘地理信息周讯》整期长图做中文 OCR，输出与图片同名的 .txt。
const path = require("path");
const fs = require("fs");

const ROOT = path.resolve(__dirname, "..");
const WEEKLY = path.join(ROOT, "03_参考_山东周讯");
// 语言模型缓存放在脚本目录，避免运行后在项目根目录留下 chi_sim.traineddata
const CACHE = path.join(__dirname, ".tessdata");

function pageImages() {
  const out = [];
  for (const dir of fs.readdirSync(WEEKLY)) {
    if (!/^第\d+期$/.test(dir)) continue;
    const abs = path.join(WEEKLY, dir);
    for (const f of fs.readdirSync(abs).filter((x) => /^p\d+\.jpg$/.test(x)).sort()) {
      out.push({ issue: dir, img: path.join(abs, f), txt: path.join(abs, f.replace(/\.jpg$/, ".txt")) });
    }
  }
  return out;
}

(async () => {
  const jobs = pageImages().filter((j) => !(fs.existsSync(j.txt) && fs.statSync(j.txt).size > 50));
  if (!jobs.length) {
    console.log("OCR 已是最新，无需处理");
    return;
  }
  console.log(`待 OCR ${jobs.length} 页`);
  const { createWorker } = require("tesseract.js");
  const worker = await createWorker("chi_sim", 1, { cachePath: CACHE });
  let done = 0;
  for (const job of jobs) {
    try {
      const { data } = await worker.recognize(job.img);
      fs.writeFileSync(job.txt, (data.text || "").trim() + "\n", "utf8");
      done += 1;
      if (done % 10 === 0 || done === jobs.length) console.log(`  已处理 ${done}/${jobs.length}`);
    } catch (err) {
      console.log(`  ! ${job.img} :: ${String(err).slice(0, 120)}`);
    }
  }
  await worker.terminate();
  console.log("OCR 完成");
})();
