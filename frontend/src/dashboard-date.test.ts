import {expect,it} from 'vitest';
import {formatDashboardDate} from './DashboardSession';
it('displays a full month name',()=>{
 expect(formatDashboardDate(new Date('2026-11-05T12:00:00Z'))).toBe('5 November 2026');
});
it('uses the India date when UTC is on the previous day',()=>{
 expect(formatDashboardDate(new Date('2026-12-31T20:00:00Z'))).toBe('1 January 2027');
});
