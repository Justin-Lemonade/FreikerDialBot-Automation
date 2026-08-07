import { describe, expect, it } from 'vitest';
import { findCommand, parseCommandInput } from '../commandParser';

describe('parseCommandInput', () => {
  it('splits a command name from its argument', () => {
    expect(parseCommandInput('search 4021 main st')).toEqual({ name: 'search', arg: '4021 main st' });
  });

  it('lowercases the command name but not the argument', () => {
    expect(parseCommandInput('SEARCH Main St')).toEqual({ name: 'search', arg: 'Main St' });
  });

  it('handles a command with no argument', () => {
    expect(parseCommandInput('pause')).toEqual({ name: 'pause', arg: '' });
  });

  it('collapses repeated whitespace between name and argument', () => {
    expect(parseCommandInput('export   csv')).toEqual({ name: 'export', arg: 'csv' });
  });

  it('trims leading/trailing whitespace', () => {
    expect(parseCommandInput('  help  ')).toEqual({ name: 'help', arg: '' });
  });

  it('returns an empty name for blank input', () => {
    expect(parseCommandInput('')).toEqual({ name: '', arg: '' });
    expect(parseCommandInput('   ')).toEqual({ name: '', arg: '' });
  });
});

describe('findCommand', () => {
  const commands = [
    { name: 'stats', aliases: ['statistics', 'summary'] },
    { name: 'search', aliases: ['find', 'customer'] },
  ];

  it('finds a command by its primary name', () => {
    expect(findCommand(commands, 'stats')).toBe(commands[0]);
  });

  it('finds a command by an alias', () => {
    expect(findCommand(commands, 'find')).toBe(commands[1]);
    expect(findCommand(commands, 'summary')).toBe(commands[0]);
  });

  it('returns undefined for an unknown command', () => {
    expect(findCommand(commands, 'nonexistent')).toBeUndefined();
  });

  it('is case-sensitive (callers must lowercase first, as parseCommandInput does)', () => {
    expect(findCommand(commands, 'STATS')).toBeUndefined();
  });
});
