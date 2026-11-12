// 사이트 스타일(tw.css)을 만들 때 쓰는 Tailwind 설정. 클래스를 찾아볼 파일 목록이 content 에 있다.
// tw.css 는 .github/workflows/build-pages.yml 이 index.html 이 바뀔 때마다 다시 만든다.
module.exports = {
  darkMode: 'class',
  content: ['./index.html', './scripts/build_pages.py'],
  plugins: [require('@tailwindcss/typography')],
};
