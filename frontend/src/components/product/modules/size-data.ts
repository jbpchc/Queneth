// Plain data (no "use client"), so server components such as CategoryModule
// can import it. An array exported from a client module reaches a server
// component as a client reference, not an array.

/** EU → UK → US women → US men → foot length (cm). */
export const SHOE_SIZES: [number, number, number, number, number][] = [
  [35, 2.5, 5, 3.5, 22.5], [36, 3.5, 6, 4.5, 23], [37, 4, 6.5, 5, 23.5], [38, 5, 7.5, 6, 24],
  [39, 6, 8.5, 6.5, 25], [40, 6.5, 9, 7, 25.5], [41, 7.5, 10, 8, 26], [42, 8, 10.5, 8.5, 26.5],
  [43, 9, 11.5, 9.5, 27.5], [44, 9.5, 12, 10, 28], [45, 10.5, 13, 11, 28.5], [46, 11, 13.5, 12, 29],
];

