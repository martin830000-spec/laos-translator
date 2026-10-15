import html from './index.html';
// Import the exact P168A JSON bytes; the browser verifies their locked Git-blob SHA.
import promptConfigRaw from '../../../prompt-config.json';
import {createGateway,R4Budget} from './gateway-core.mjs';
export {R4Budget};
export default createGateway({html,promptConfigRaw});
