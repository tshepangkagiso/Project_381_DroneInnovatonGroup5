// Gulp tasks
//
// Usage:
//
// 1. Build sass files in sass folder without any minifications
//    npm run gulp
//
// 2. Build and minify files into dist
//    npm run gulp build

const gulp = require('gulp');
const sass = require('gulp-sass')(require('sass'));
const browserSync = require('browser-sync').create();
const terser = require('gulp-terser');
const cssminify = require('gulp-clean-css');
const htmlmin = require('gulp-htmlmin');
const del = require('del');
const jsonminify = require('gulp-jsonminify');

let output = 'src';

gulp.task('copy:font', function (callback) {
  return gulp.src('src/font/**/*').pipe(gulp.dest(output + '/font'));
});
gulp.task('copy:vendorcss', function (callback) {
  return gulp.src('src/css/vendor/*').pipe(gulp.dest(output + '/css/vendor'));
});
gulp.task('copy:img', function (callback) {
  return gulp.src('src/img/**/*').pipe(gulp.dest(output + '/img'));
});
gulp.task('copy:js', function (callback) {
  return gulp.src('src/js/**/*').pipe(gulp.dest(output + '/js'));
});
gulp.task('copy:json', function (callback) {
  return gulp.src('src/json/*').pipe(gulp.dest(output + '/json'));
});
gulp.task('copy:favicon', function (callback) {
  return gulp.src('src/favicon.ico').pipe(gulp.dest(output)).pipe(gulp.dest(output));
});
gulp.task('copy:html', function (callback) {
  return gulp.src('src/*.html').pipe(gulp.dest(output));
});

gulp.task('build:sass', function (callback) {
  return gulp
    .src('src/sass/*.scss')
    .pipe(sass())
    .pipe(gulp.dest(output + '/css'));
});


gulp.task('minify:js', function (callback) {
  return gulp
    .src(['src/js/**/*.js', '!src/js/**/*.min.js'])
    .pipe(terser())
    .pipe(gulp.dest(output + '/js'));
});

gulp.task('minify:json', function (callback) {
  return gulp
    .src('src/json/*')
    .pipe(jsonminify())
    .pipe(gulp.dest(output + '/json'));
});

gulp.task('minify:sass', function (callback) {
  return gulp
    .src('src/sass/*.scss')
    .pipe(sass())
    .pipe(cssminify({zindex: false}))
    .pipe(gulp.dest(output + '/css'));
});
gulp.task('minify:css', function (callback) {
  return gulp.src('src/css/*.css').pipe(cssminify({zindex: false})).pipe(gulp.dest(output + '/css'));
});

gulp.task('minify:html', function (callback) {
  return gulp
    .src('src/*.html')
    .pipe(htmlmin({collapseWhitespace: true, preserveLineBreaks: true, removeComments: true}))
    .pipe(gulp.dest(output));
});



gulp.task('reload', function (callback) {
  browserSync.reload();
  callback();
});

gulp.task('sync', function (callback) {
  browserSync.init({
    server: {
      baseDir: output,
    },
    notify: false,
    startPath: '/index.html',
  });
  callback();
});

gulp.task('watch', function (callback) {
  gulp.watch('src/sass/**/*', gulp.series('build:sass', 'reload'));
  gulp.watch('src/js/**/*.js', gulp.series('reload'));
  gulp.watch('src/css/**/*', gulp.series('reload'));
  gulp.watch('src/json/**/*', gulp.series('reload'));
  gulp.watch('src/font/**/*', gulp.series('reload'));
  gulp.watch('src/img/**/*', gulp.series('reload'));
  gulp.watch('src/*.html', gulp.series('reload'));
  callback();
});

gulp.task('clean:output', function (callback) {
  return del(output);
});

gulp.task('mode:dev', function (callback) {
  output = 'src';
  callback();
});

gulp.task('mode:build', function (callback) {
  output = 'dist';
  callback();
});



gulp.task('default', gulp.series('mode:dev', 'build:sass', gulp.parallel('sync', 'watch')));

gulp.task('build', gulp.series('mode:build', 'clean:output', 'copy:font', 'copy:vendorcss','minify:css', 'copy:img', 'minify:json', 'copy:favicon', 'copy:js', 'minify:js', 'minify:sass', 'minify:html')
);
