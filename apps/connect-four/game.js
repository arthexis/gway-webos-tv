/* Connect Four rules, Stage A. Copyright (c) 2026 Arthexis. MIT License.
 * No renderer, remote binding, or computer opponent is included in this module.
 * Coordinates are zero-based; row 0 is at the top, row 5 at the bottom.
 */
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.ConnectFourRules = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  var ROWS = 6;
  var COLUMNS = 7;
  var DIRECTIONS = [[0, 1], [1, 0], [1, 1], [1, -1]];

  function createGame() {
    return {
      board: Array.from({ length: ROWS }, function () { return Array(COLUMNS).fill(null); }),
      turn: 'red', status: 'playing', winner: null, winningLine: null, moves: []
    };
  }

  function validColumn(column) {
    return Number.isInteger(column) && column >= 0 && column < COLUMNS;
  }

  function landingRow(board, column) {
    if (!validColumn(column)) return -1;
    for (var row = ROWS - 1; row >= 0; row--) {
      if (board[row][column] === null) return row;
    }
    return -1;
  }

  function legalColumns(board) {
    var out = [];
    for (var c = 0; c < COLUMNS; c++) if (landingRow(board, c) !== -1) out.push(c);
    return out;
  }

  // A label must occupy the actual next landing cell, never a separate header row.
  function landingTargets(board) {
    return legalColumns(board).map(function (c) {
      return { row: landingRow(board, c), column: c, number: c + 1 };
    });
  }

  function inBounds(row, column) {
    return row >= 0 && row < ROWS && column >= 0 && column < COLUMNS;
  }

  // Return one deterministic four-chip segment containing the last placed chip.
  function winningSegment(board, row, column) {
    if (!inBounds(row, column) || board[row][column] === null) return null;
    var player = board[row][column].player;
    for (var d = 0; d < DIRECTIONS.length; d++) {
      var dr = DIRECTIONS[d][0];
      var dc = DIRECTIONS[d][1];
      var cells = [];
      for (var step = -3; step <= 3; step++) {
        var r = row + step * dr;
        var c = column + step * dc;
        if (!inBounds(r, c) || board[r][c] === null || board[r][c].player !== player) {
          // Opponent/empty slots interrupt a contiguous streak; collect separately below.
          continue;
        }
        cells.push({ row: r, column: c, step: step });
      }
      // Only consecutive steps count as contiguous chips.
      for (var i = 0; i <= cells.length - 4; i++) {
        var part = cells.slice(i, i + 4);
        if (part[3].step - part[0].step === 3 &&
            part.some(function (x) { return x.step === 0; })) {
          return part.map(function (x) { return { row: x.row, column: x.column }; });
        }
      }
    }
    return null;
  }

  function applyMove(state, column, assisted) {
    if (!state || state.status !== 'playing' || !validColumn(column)) return state;
    var row = landingRow(state.board, column);
    if (row === -1) return state;
    var nextBoard = state.board.map(function (r) { return r.slice(); });
    var disc = { player: state.turn, assisted: assisted === true };
    nextBoard[row][column] = disc;
    var line = winningSegment(nextBoard, row, column);
    var full = legalColumns(nextBoard).length === 0;
    var status = line ? 'won' : full ? 'draw' : 'playing';
    return {
      board: nextBoard,
      turn: status === 'playing' ? (state.turn === 'red' ? 'yellow' : 'red') : state.turn,
      status: status,
      winner: line ? state.turn : null,
      winningLine: line,
      moves: state.moves.concat([{ row: row, column: column, player: state.turn, assisted: disc.assisted }])
    };
  }

  // The future Play key handler may only reset a terminal game.
  function restartAfterTerminal(state) {
    return state && (state.status === 'won' || state.status === 'draw') ? createGame() : state;
  }

  return {
    ROWS: ROWS, COLUMNS: COLUMNS, createGame: createGame,
    landingRow: landingRow, landingTargets: landingTargets,
    legalColumns: legalColumns, winningSegment: winningSegment,
    applyMove: applyMove, restartAfterTerminal: restartAfterTerminal
  };
}));
