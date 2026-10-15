import html from './index.html';
import promptConfig from '../../../prompt-config.json';
import {createGateway,R4Budget} from './gateway-core.mjs';
export {R4Budget};
export default createGateway({html,promptConfig});
