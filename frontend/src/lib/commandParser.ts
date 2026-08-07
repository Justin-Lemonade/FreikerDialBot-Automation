/** Splits typed input like "search 4021 main st" into a lowercased
 * command name ("search") and the remaining free-text argument
 * ("4021 main st"). Whitespace-only input yields an empty name. Pure
 * and side-effect-free so it's testable without rendering Commands.tsx
 * or mocking the API client -- the parsing logic and the command
 * table's side effects (navigation, API calls) are deliberately kept
 * separate. */
export const parseCommandInput = (raw: string): { name: string; arg: string } => {
  const trimmed = raw.trim();
  if (!trimmed) return { name: '', arg: '' };
  const [nameToken, ...rest] = trimmed.split(/\s+/);
  return { name: nameToken.toLowerCase(), arg: rest.join(' ') };
};

export interface NamedCommand {
  name: string;
  aliases: string[];
}

/** Finds a command by exact name or alias match (case-sensitive on the
 * already-lowercased `name` from parseCommandInput). Returns undefined
 * for no match -- callers are responsible for the "unknown command"
 * error message, this only does lookup. */
export const findCommand = <T extends NamedCommand>(commands: T[], name: string): T | undefined =>
  commands.find((command) => command.name === name || command.aliases.includes(name));
