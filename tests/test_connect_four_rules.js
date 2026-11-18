'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const game = require('../apps/connect-four/game.js');

function moves(columns, initial = game.createGame()) {
  return columns.reduce((state, col) => game.applyMove(state, col), initial);
}
function boardFromRows(rows) {
  return rows.map(row => Array.from(row, ch =>
    ch === '.' ? null : {player: ch === 'R' ? 'red' : 'yellow', assisted: false}));
}

test('empty 7x6 board, red starts, labels in lowest empty cells', () => {
  const s = game.createGame();
  assert.equal(s.board.length, 6);
  assert(s.board.every(r => r.length === 7 && r.every(x => x === null)));
  assert.equal(s.turn, 'red');
  assert.equal(s.status, 'playing');
  assert.deepEqual(game.landingTargets(s.board), Array.from({length: 7}, (_, c) => ({row: 5, column: c, number: c + 1})));
});

test('gravity, alternation, and assisted chip metadata; original state not mutated', () => {
  const old = game.createGame();
  const red = game.applyMove(old, 3);
  const yellow = game.applyMove(red, 3, true);
  assert.equal(old.board[5][3], null);
  assert.equal(red.board[5][3].player, 'red');
  assert.equal(yellow.board[4][3].player, 'yellow');
  assert.equal(yellow.board[4][3].assisted, true);
  assert.equal(yellow.turn, 'red');
  assert.equal(yellow.moves.length, 2);
  assert.equal(game.landingRow(yellow.board, 3), 3);
  assert(game.landingTargets(yellow.board).some(x => x.column === 3 && x.row === 3 && x.number === 4));
  assert(!game.landingTargets(yellow.board).some(x => x.column === 3 && x.row === 5));
});

test('six chips fill one column; seventh request has no effect or turn advance', () => {
  let s = game.createGame();
  for (let i = 0; i < 6; i++) {
    s = game.applyMove(s, 2);
    if (i < 5) assert.equal(game.landingRow(s.board, 2), 4-i);
  }
  assert.equal(s.turn, 'red');
  assert.equal(game.landingRow(s.board, 2), -1);
  assert(!game.landingTargets(s.board).some(x => x.column === 2));
  assert.strictEqual(game.applyMove(s, 2), s);
  assert.strictEqual(game.applyMove(s, -1), s);
  assert.strictEqual(game.applyMove(s, 7), s);
  assert.strictEqual(game.applyMove(s, 1.5), s);
  assert.strictEqual(game.applyMove(s, '2'), s);
});

test('horizontal win, terminal lock and Play-style restart', () => {
  let s = moves([0,0,1,1,2,2,3]);
  assert.equal(s.status, 'won');
  assert.equal(s.winner, 'red');
  assert.deepEqual(s.winningLine, [0,1,2,3].map(column => ({row: 5, column})));
  assert.strictEqual(game.applyMove(s, 4), s);
  const reset = game.restartAfterTerminal(s);
  assert.equal(reset.status, 'playing');
  assert.equal(reset.turn, 'red');
  assert.equal(reset.moves.length, 0);
  assert.strictEqual(game.restartAfterTerminal(reset), reset);
});

test('vertical win', () => {
  const s = moves([2,3,2,3,2,3,2]);
  assert.equal(s.status, 'won');
  assert.equal(s.winner, 'red');
  assert.deepEqual(s.winningLine, [2,3,4,5].map(row => ({row, column: 2})));
});

test('both diagonal directions contain exactly four centers, deterministically', () => {
  const diag1 = boardFromRows([
    '.......','.......','...R...','..R....','.R.....','R......'
  ]);
  assert.deepEqual(game.winningSegment(diag1, 2, 3), [{row:2,column:3},{row:3,column:2},{row:4,column:1},{row:5,column:0}]);
  const diag2 = boardFromRows([
    '.......','.......','...R...','....R..','.....R.','......R'
  ]);
  assert.deepEqual(game.winningSegment(diag2, 2, 3), [{row:2,column:3},{row:3,column:4},{row:4,column:5},{row:5,column:6}]);
});

test('line finder does not bridge gaps or opponents', () => {
  const b = boardFromRows([
    '.......','.......','.......','.......','.......','RR.RRR.'
  ]);
  assert.equal(game.winningSegment(b, 5, 4), null);
  b[5][2] = {player:'yellow',assisted:false};
  assert.equal(game.winningSegment(b, 5, 3), null);
});

test('draw on full board with no winner; terminal board wins take priority over draw', () => {
  const board = boardFromRows([
    'RRYYRRY', 'YYRRYYR', 'RRYYRRY', 'YYRRYYR', 'RRYYRRY', 'YYRRYYR'
  ]);
  for (let r = 0; r < 6; r++) for (let c = 0; c < 7; c++) {
    assert.equal(game.winningSegment(board,r,c), null, 'unexpected line at ' + r + ',' + c);
  }
  const s = { ...game.createGame(), board: board.map(r => r.slice()), turn:'red' };
  s.board[0][0] = null;
  const last = game.applyMove(s,0);
  assert.equal(last.status, 'draw');
  assert.equal(last.winner, null);
  assert.equal(game.legalColumns(last.board).length, 0);
  assert.equal(game.restartAfterTerminal(last).turn, 'red');
});

test('Yellow can win vertically on its fourth turn', () => {
  const s = moves([0,3,0,3,1,3,1,3]);
  assert.equal(s.status, 'won');
  assert.equal(s.winner, 'yellow');
  assert.deepEqual(s.winningLine, [2,3,4,5].map(row => ({row, column:3})));
});

test('both diagonal wins can arise from legal alternating gravity moves', () => {
  const downRight = moves([5,2,2,4,3,1,4,3,3,2,2]);
  assert.equal(downRight.status, 'won');
  assert.equal(downRight.winner, 'red');
  assert.equal(Math.abs(downRight.winningLine[0].row-downRight.winningLine[3].row), 3);
  assert.equal(Math.abs(downRight.winningLine[0].column-downRight.winningLine[3].column), 3);
  const downLeft = moves([0,0,6,2,0,2,2,3,6,3,5,1,1,2,1,6,4,4,2,6,5,5]);
  assert.equal(downLeft.status, 'won');
  assert.equal(downLeft.winner, 'yellow');
  assert.equal(Math.abs(downLeft.winningLine[0].row-downLeft.winningLine[3].row), 3);
  assert.equal(Math.abs(downLeft.winningLine[0].column-downLeft.winningLine[3].column), 3);
});

test('a winning move on the 42nd cell reports win rather than draw', () => {
  const board = boardFromRows([
    '.RRRYYY', 'YYRRYYR', 'RRYYRRY', 'YYRRYYR', 'RRYYRRY', 'YYRRYYR'
  ]);
  const previous = {...game.createGame(), board, turn:'red'};
  const last = game.applyMove(previous, 0);
  assert.equal(last.status, 'won');
  assert.equal(last.winner, 'red');
  assert.equal(last.winningLine.length, 4);
  assert.equal(game.legalColumns(last.board).length, 0);
});
