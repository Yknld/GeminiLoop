#!/usr/bin/env node
/**
 * Playwright MCP Server
 * 
 * Implements Model Context Protocol for Playwright browser automation
 * Communicates via JSON-RPC 2.0 over stdio
 */

const { chromium } = require('playwright');
const readline = require('readline');

class MCPServer {
  constructor() {
    this.browser = null;
    this.context = null;
    this.page = null;
    this.messageId = 0;
    this.videoPath = null;
    this.recording = false;
    this.consoleMessages = [];  // Store console messages
    
    // Setup stdio communication
    this.rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
      terminal: false
    });
    
    this.log('Playwright MCP Server starting...');
  }
  
  log(message) {
    console.error(`[MCP Server] ${message}`);
  }
  
  async start() {
    this.log('MCP Server ready');
    
    // Listen for JSON-RPC requests
    this.rl.on('line', async (line) => {
      try {
        const request = JSON.parse(line);
        await this.handleRequest(request);
      } catch (error) {
        this.log(`Parse error: ${error.message}`);
        this.sendError(null, -32700, 'Parse error');
      }
    });
  }
  
  async handleRequest(request) {
    const { id, method, params } = request;
    
    this.log(`Request: ${method}`);
    
    try {
      let result;
      
      switch (method) {
        case 'initialize':
          result = await this.initialize(params);
          break;
        
        case 'tools/list':
          result = await this.listTools();
          break;
        
        case 'tools/call':
          result = await this.callTool(params);
          break;
        
        case 'notifications/initialized':
          return;
        
        default:
          throw new Error(`Unknown method: ${method}`);
      }
      
      this.sendResponse(id, result);
      
    } catch (error) {
      this.log(`Error: ${error.message}`);
      this.sendError(id, -32603, error.message);
    }
  }
  
  async initialize(params) {
    this.log('Initializing...');
    
    const headless = process.env.HEADLESS !== 'false';
    const visibleBrowser = process.env.VISIBLE_BROWSER === '1';
    
    // Use visible mode if VISIBLE_BROWSER is set
    const shouldBeHeadless = visibleBrowser ? false : headless;
    
    this.log(`   Headless: ${shouldBeHeadless}`);
    this.log(`   Visible browser: ${visibleBrowser}`);
    if (visibleBrowser) {
      this.log(`   Display: ${process.env.DISPLAY || ':99'}`);
    }
    
    this.browser = await chromium.launch({
      headless: shouldBeHeadless,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu'
      ]
    });
    
    // Create context with video recording enabled (will be started when needed)
    this.context = await this.browser.newContext({
      viewport: { width: 1440, height: 900 },
      recordVideo: {
        dir: process.env.VIDEO_DIR || '/tmp/playwright-videos',
        size: { width: 1440, height: 900 }
      }
    });
    
    this.page = await this.context.newPage();
    
    // Setup console message collection
    this.consoleMessages = [];
    this.page.on('console', (msg) => {
      const message = {
        type: msg.type(),
        text: msg.text(),
        timestamp: Date.now(),
        location: msg.location() ? {
          url: msg.location().url,
          lineNumber: msg.location().lineNumber,
          columnNumber: msg.location().columnNumber
        } : null
      };
      this.consoleMessages.push(message);
      // Keep only last 1000 messages to prevent memory issues
      if (this.consoleMessages.length > 1000) {
        this.consoleMessages.shift();
      }
    });
    
    // Setup page error collection
    this.page.on('pageerror', (error) => {
      this.consoleMessages.push({
        type: 'error',
        text: error.message,
        stack: error.stack,
        timestamp: Date.now(),
        location: null
      });
    });
    
    if (visibleBrowser) {
      this.log('Browser launched in VISIBLE mode');
      this.log('   View at: http://localhost:6080/vnc.html (password: secret)');
    } else {
      this.log('Browser launched');
    }
    
    return {
      protocolVersion: '2024-11-05',
      serverInfo: {
        name: 'playwright-mcp-server',
        version: '1.0.0'
      },
      capabilities: {
        tools: {}
      }
    };
  }
  
  async listTools() {
    return {
      tools: [
        {
          name: 'browser_navigate',
          description: 'Navigate to a URL',
          inputSchema: {
            type: 'object',
            properties: {
              url: { type: 'string' }
            },
            required: ['url']
          }
        },
        {
          name: 'browser_take_screenshot',
          description: 'Take a screenshot',
          inputSchema: {
            type: 'object',
            properties: {
              fullPage: { type: 'boolean' },
              filename: { type: 'string' }
            }
          }
        },
        {
          name: 'browser_snapshot',
          description: 'Get page snapshot',
          inputSchema: {
            type: 'object',
            properties: {}
          }
        },
        {
          name: 'browser_console_messages',
          description: 'Get console messages',
          inputSchema: {
            type: 'object',
            properties: {}
          }
        },
        {
          name: 'browser_evaluate',
          description: 'Evaluate JavaScript expression',
          inputSchema: {
            type: 'object',
            properties: {
              expression: { type: 'string', description: 'JavaScript to evaluate' }
            },
            required: ['expression']
          }
        },
        {
          name: 'browser_wait',
          description: 'Wait for duration',
          inputSchema: {
            type: 'object',
            properties: {
              duration: { type: 'number', description: 'Milliseconds to wait' }
            },
            required: ['duration']
          }
        },
        {
          name: 'browser_click',
          description: 'Click an element by CSS selector',
          inputSchema: {
            type: 'object',
            properties: {
              selector: { type: 'string', description: 'CSS selector for the element to click' }
            },
            required: ['selector']
          }
        },
        {
          name: 'browser_type',
          description: 'Type text into an input field',
          inputSchema: {
            type: 'object',
            properties: {
              selector: { type: 'string', description: 'CSS selector for the input field' },
              text: { type: 'string', description: 'Text to type' }
            },
            required: ['selector', 'text']
          }
        },
        {
          name: 'browser_start_recording',
          description: 'Start video recording',
          inputSchema: {
            type: 'object',
            properties: {
              videoPath: { type: 'string', description: 'Path to save video file' }
            },
            required: ['videoPath']
          }
        },
        {
          name: 'browser_stop_recording',
          description: 'Stop video recording and save to file',
          inputSchema: {
            type: 'object',
            properties: {}
          }
        }
      ]
    };
  }
  
  async callTool(params) {
    const { name, arguments: args } = params;
    
    this.log(`Tool: ${name}`);
    
    switch (name) {
      case 'browser_navigate':
        return await this.navigate(args.url);
      
      case 'browser_take_screenshot':
        return await this.screenshot(args.fullPage, args.filename);
      
      case 'browser_snapshot':
        return await this.snapshot();
      
      case 'browser_console_messages':
        return await this.getConsole();
      
      case 'browser_evaluate':
        return await this.evaluate(args.expression);
      
      case 'browser_wait':
        return await this.wait(args.duration);
      
      case 'browser_click':
        return await this.click(args.selector);
      
      case 'browser_type':
        return await this.type(args.selector, args.text);
      
      case 'browser_start_recording':
        return await this.startRecording(args.videoPath);
      
      case 'browser_stop_recording':
        return await this.stopRecording();
      
      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  }
  
  async navigate(url) {
    this.log(`Navigating to: ${url}`);
    await this.page.goto(url, { waitUntil: 'networkidle' });
    
    const title = await this.page.title();
    this.log(`Loaded: ${title}`);
    
    return {
      success: true,
      title,
      url: this.page.url()
    };
  }
  
  async screenshot(fullPage = true, filename, timeout = 10000) {
    this.log(`Taking screenshot: ${filename}`);
    
    try {
      // Wait for page to be in a stable state before screenshot
      // This helps avoid font loading timeouts
      try {
        await this.page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {
          // If networkidle times out, just proceed - page might be stable enough
          this.log('Network idle wait timed out, proceeding with screenshot');
        });
      } catch (e) {
        // Ignore networkidle timeout, proceed with screenshot
      }
      
      // Take screenshot with timeout
      await this.page.screenshot({
        path: filename,
        fullPage,
        timeout: timeout,
        animations: 'disabled' // Disable animations for faster screenshots
      });
      
      this.log('Screenshot saved');
      
      return {
        success: true,
        path: filename
      };
    } catch (error) {
      // If screenshot fails due to timeout, try again with shorter timeout
      if (error.message.includes('Timeout') || error.message.includes('timeout')) {
        this.log(`Screenshot timeout, retrying with shorter timeout (5s)...`);
        try {
          // Don't wait for networkidle on retry, just take screenshot quickly
          await this.page.screenshot({
            path: filename,
            fullPage,
            timeout: 5000,
            animations: 'disabled'
          });
          this.log('Screenshot saved (retry)');
          return {
            success: true,
            path: filename
          };
        } catch (retryError) {
          this.log(`Screenshot retry failed: ${retryError.message}`);
          // Try one more time with very short timeout (2s) - just capture what's there
          try {
            this.log(`Final retry with minimal timeout (2s)...`);
            await this.page.screenshot({
              path: filename,
              fullPage,
              timeout: 2000,
              animations: 'disabled'
            });
            this.log('Screenshot saved (final retry)');
            return {
              success: true,
              path: filename
            };
          } catch (finalError) {
            this.log(`All screenshot attempts failed: ${finalError.message}`);
            throw finalError;
          }
        }
      }
      throw error;
    }
  }
  
  async snapshot() {
    this.log('Getting snapshot...');
    
    const title = await this.page.title();
    const textContent = await this.page.evaluate(() => document.body.innerText);
    const buttons = await this.page.$$eval('button', btns => 
      btns.map(b => b.textContent.trim())
    );
    
    this.log(`Snapshot: ${buttons.length} buttons`);
    
    return {
      title,
      textContent,
      buttons,
      buttonCount: buttons.length
    };
  }
  
  async getConsole() {
    this.log(`Getting console messages... (${this.consoleMessages.length} stored)`);
    
    // Return all stored messages
    const messages = this.consoleMessages.map(msg => ({
      type: msg.type,
      message: msg.text || msg.message || '',
      timestamp: msg.timestamp,
      location: msg.location
    }));
    
    return {
      messages: messages,
      count: messages.length,
      errors: messages.filter(m => m.type === 'error').length,
      warnings: messages.filter(m => m.type === 'warning').length
    };
  }
  
  async evaluate(expression) {
    this.log(`Evaluating: ${expression.substring(0, 50)}...`);
    
    try {
      const result = await this.page.evaluate(expression);
      
      this.log('Evaluation complete');
      
      return {
        success: true,
        result
      };
    } catch (error) {
      this.log(`Evaluation failed: ${error.message}`);
      
      return {
        success: false,
        error: error.message
      };
    }
  }
  
  async wait(duration) {
    this.log(`Waiting ${duration}ms...`);
    
    await this.page.waitForTimeout(duration);
    
    this.log('Wait complete');
    
    return {
      success: true,
      duration
    };
  }
  
  async click(selector) {
    this.log(`Clicking: ${selector}`);
    
    try {
      await this.page.click(selector);
      this.log('Click successful');
      
      return {
        success: true,
        selector
      };
    } catch (error) {
      this.log(`Click failed: ${error.message}`);
      
      return {
        success: false,
        error: error.message,
        selector
      };
    }
  }
  
  async type(selector, text) {
    this.log(`Typing into ${selector}: ${text.substring(0, 50)}...`);
    
    try {
      await this.page.fill(selector, text);
      this.log('Type successful');
      
      return {
        success: true,
        selector,
        textLength: text.length
      };
    } catch (error) {
      this.log(`Type failed: ${error.message}`);
      
      return {
        success: false,
        error: error.message,
        selector
      };
    }
  }
  
  async startRecording(videoPath) {
    this.log(`Starting video recording: ${videoPath}`);
    
    try {
      // Close current page and context
      if (this.page) {
        await this.page.close();
      }
      if (this.context) {
        await this.context.close();
      }
      
      // Create new context with video recording
      const fs = require('fs');
      const path = require('path');
      const videoDir = path.dirname(videoPath);
      if (!fs.existsSync(videoDir)) {
        fs.mkdirSync(videoDir, { recursive: true });
      }
      
      this.context = await this.browser.newContext({
        viewport: { width: 1440, height: 900 },
        recordVideo: {
          dir: videoDir,
          size: { width: 1440, height: 900 }
        }
      });
      
      this.page = await this.context.newPage();
      this.videoPath = videoPath;
      this.recording = true;
      
      this.log('Video recording started');
      
      return {
        success: true,
        videoPath
      };
    } catch (error) {
      this.log(`Start recording failed: ${error.message}`);
      
      return {
        success: false,
        error: error.message
      };
    }
  }
  
  async stopRecording() {
    this.log('Stopping video recording...');
    
    try {
      if (!this.recording || !this.context) {
        return {
          success: false,
          error: 'No recording in progress'
        };
      }
      
      // Close context to finalize video
      await this.context.close();
      
      // Get the video file path (Playwright saves it automatically)
      // The video is saved when context closes, we need to find it
      const fs = require('fs');
      const path = require('path');
      const videoDir = path.dirname(this.videoPath);
      
      // Playwright saves videos with a hash, find the most recent one
      let videoFile = null;
      if (fs.existsSync(videoDir)) {
        const files = fs.readdirSync(videoDir)
          .filter(f => f.endsWith('.webm'))
          .map(f => ({
            name: f,
            path: path.join(videoDir, f),
            time: fs.statSync(path.join(videoDir, f)).mtime
          }))
          .sort((a, b) => b.time - a.time);
        
        if (files.length > 0) {
          videoFile = files[0].path;
          // Rename to desired path if different
          if (videoFile !== this.videoPath) {
            fs.renameSync(videoFile, this.videoPath);
            videoFile = this.videoPath;
          }
        }
      }
      
      // Create new context without recording for continued use
      this.context = await this.browser.newContext({
        viewport: { width: 1440, height: 900 }
      });
      this.page = await this.context.newPage();
      
      this.recording = false;
      const finalPath = videoFile || this.videoPath;
      
      this.log(`Video recording stopped: ${finalPath}`);
      
      return {
        success: true,
        videoPath: finalPath
      };
    } catch (error) {
      this.log(`Stop recording failed: ${error.message}`);
      
      return {
        success: false,
        error: error.message
      };
    }
  }
  
  sendResponse(id, result) {
    const response = {
      jsonrpc: '2.0',
      id,
      result
    };
    
    console.log(JSON.stringify(response));
  }
  
  sendError(id, code, message) {
    const response = {
      jsonrpc: '2.0',
      id,
      error: { code, message }
    };
    
    console.log(JSON.stringify(response));
  }
  
  async cleanup() {
    this.log('Cleaning up...');
    
    if (this.browser) {
      await this.browser.close();
      this.log('Browser closed');
    }
  }
}

// Start server
const server = new MCPServer();
server.start();

// Handle cleanup on exit
process.on('SIGTERM', async () => {
  await server.cleanup();
  process.exit(0);
});

process.on('SIGINT', async () => {
  await server.cleanup();
  process.exit(0);
});
