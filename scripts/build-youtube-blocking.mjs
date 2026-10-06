import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { RuleParser } from '@adguard/agtree/parser';
import { QuoteUtils } from '@adguard/agtree';
import { scriptlets, SCRIPTLETS_VERSION } from '@adguard/scriptlets';

const sourceDirectory = new URL('../firefox-ios/Client/Frontend/UserContent/AdBlocking/', import.meta.url);
const supportedDomains = ['youtube.com', 'youtube-nocookie.com', 'youtubekids.com'];

export function compileYouTubeRules(text) {
  const rules = text.split('\n').map(line => line.trim()).filter(line => line && !line.startsWith('!'));
  const output = rules.map((line, index) => {
    const rule = RuleParser.parse(line);
    if (rule.exception || !['ScriptletInjectionRule', 'JsInjectionRule'].includes(rule.type)) {
      throw new Error(`Unsupported YouTube rule ${index + 1}`);
    }
    const domains = rule.domains.children.map(domain => {
      if (domain.exception || !supportedDomains.some(root => domain.value === root || domain.value.endsWith('.' + root))) {
        throw new Error(`Unexpected YouTube domain: ${domain.value}`);
      }
      return domain.value;
    });
    if (!domains.length) throw new Error('Unscoped YouTube rule');
    let condition = `${JSON.stringify(domains)}.some(matchesHost)`;
    for (const modifier of rule.modifiers?.children ?? []) {
      if (modifier.name.value !== 'path' || modifier.exception || modifier.value?.value !== '/tv') {
        throw new Error('Unsupported YouTube rule modifier');
      }
      condition += ' && location.pathname.includes("/tv")';
    }
    const code = rule.type === 'JsInjectionRule' ? rule.body.value : rule.body.children.map(parameters => {
      const [name, ...args] = parameters.children.map(parameter => QuoteUtils.removeQuotesAndUnescape(parameter.value));
      return scriptlets.invoke({
        name, args, engine: 'extension', version: SCRIPTLETS_VERSION,
        verbose: false, uniqueId: 'ffox-youtube-' + index,
      });
    }).join('\n');
    return `if (${condition}) { try { ${code}\n } catch (error) { console.warn("FFox YouTube rule ${index + 1} failed", error); } }`;
  });
  return `(() => {
    if (location.protocol !== 'https:' && location.protocol !== 'http:') return;
    const host = location.hostname.toLowerCase();
    const matchesHost = domain => host === domain || host.endsWith('.' + domain);
    if (!${JSON.stringify(supportedDomains)}.some(matchesHost)) return;
    ${output.join('\n')}
  })();`;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const rules = readFileSync(new URL('youtube-filter-rules.txt', sourceDirectory), 'utf8');
  const license = readFileSync(new URL('LICENSE', sourceDirectory), 'utf8');
  const output = new URL('../firefox-ios/Client/Assets/YouTubeAdBlocking.js', import.meta.url);
  writeFileSync(output, `/*! AdGuard Scriptlets ${SCRIPTLETS_VERSION} and AdGuard YouTube filters.\n${license}\n*/\n${compileYouTubeRules(rules)}`);
  console.log(`Generated ${fileURLToPath(output)}`);
}
