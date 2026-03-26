#!/usr/bin/env python3
"""
Post-install script to permanently disable FastMCP session validation.
This modifies FastMCP's source code directly to remove session ID validation.
This ensures the fix persists across package reinstalls and works in Cloud Run.
"""

import os
import sys
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def find_fastmcp_installation():
    """Find where FastMCP is installed."""
    try:
        import mcp.server.streamable_http
        fastmcp_path = Path(mcp.server.streamable_http.__file__).parent.parent
        logger.info(f"Found FastMCP installation at: {fastmcp_path}")
        return fastmcp_path
    except ImportError as e:
        logger.warning(f"Could not import FastMCP: {e}")
        logger.info("Trying to find FastMCP in common locations...")
        
        # Try to find in site-packages
        import sys
        import site
        
        # Check all site-packages directories
        for site_dir in site.getsitepackages() + [site.getusersitepackages()]:
            potential_path = Path(site_dir) / "mcp" / "server" / "streamable_http.py"
            if potential_path.exists():
                fastmcp_path = potential_path.parent.parent
                logger.info(f"Found FastMCP installation at: {fastmcp_path}")
                return fastmcp_path
        
        # Check in sys.path
        for path_str in sys.path:
            potential_path = Path(path_str) / "mcp" / "server" / "streamable_http.py"
            if potential_path.exists():
                fastmcp_path = potential_path.parent.parent
                logger.info(f"Found FastMCP installation at: {fastmcp_path}")
                return fastmcp_path
        
        logger.error("FastMCP not found in any common location.")
        logger.error(f"Python executable: {sys.executable}")
        logger.error(f"Python path: {sys.path}")
        return None


def patch_streamable_http(fastmcp_path: Path):
    """Patch mcp/server/streamable_http.py to disable session validation."""
    streamable_http_file = fastmcp_path / "server" / "streamable_http.py"
    
    if not streamable_http_file.exists():
        logger.error(f"File not found: {streamable_http_file}")
        return False
    
    logger.info(f"Reading {streamable_http_file}")
    with open(streamable_http_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    changes_made = []
    
    # Check if already patched
    if '# PATCHED: Session validation disabled' in content:
        logger.info("File appears to already be patched. Verifying...")
        # Still proceed to ensure all patches are applied
    
    # Patch 1: Replace _validate_session method to always return True
    # Use line-by-line approach to avoid breaking f-strings
    lines = content.split('\n')
    new_lines = []
    i = 0
    patched_methods = set()
    
    while i < len(lines):
        line = lines[i]
        
        # Patch _validate_session
        if ('async def _validate_session' in line or 'def _validate_session' in line) and '_validate_session' not in patched_methods:
            indent = len(line) - len(line.lstrip())
            new_lines.append(line)
            i += 1
            # Skip the opening brace line if present
            if i < len(lines) and '{' in lines[i]:
                i += 1
            # Add patched body
            new_lines.append(' ' * (indent + 4) + '# PATCHED: Session validation disabled - always allow')
            new_lines.append(' ' * (indent + 4) + 'return True')
            # Skip original method body until we find the next method/class
            while i < len(lines):
                current_line = lines[i]
                if not current_line.strip():
                    i += 1
                    continue
                current_indent = len(current_line) - len(current_line.lstrip())
                if (current_indent <= indent and 
                    (current_line.strip().startswith('def ') or 
                     current_line.strip().startswith('async def ') or 
                     current_line.strip().startswith('class '))):
                    break
                i += 1
            patched_methods.add('_validate_session')
            changes_made.append("_validate_session method")
            continue
        
        # Patch _validate_request_headers
        if ('async def _validate_request_headers' in line or 'def _validate_request_headers' in line) and '_validate_request_headers' not in patched_methods:
            indent = len(line) - len(line.lstrip())
            new_lines.append(line)
            i += 1
            if i < len(lines) and '{' in lines[i]:
                i += 1
            new_lines.append(' ' * (indent + 4) + '# PATCHED: Request headers validation disabled - always allow')
            new_lines.append(' ' * (indent + 4) + 'return True')
            while i < len(lines):
                current_line = lines[i]
                if not current_line.strip():
                    i += 1
                    continue
                current_indent = len(current_line) - len(current_line.lstrip())
                if (current_indent <= indent and 
                    (current_line.strip().startswith('def ') or 
                     current_line.strip().startswith('async def ') or 
                     current_line.strip().startswith('class '))):
                    break
                i += 1
            patched_methods.add('_validate_request_headers')
            changes_made.append("_validate_request_headers method")
            continue
        
        # Patch _validate_protocol_version
        if ('async def _validate_protocol_version' in line or 'def _validate_protocol_version' in line) and '_validate_protocol_version' not in patched_methods:
            indent = len(line) - len(line.lstrip())
            new_lines.append(line)
            i += 1
            if i < len(lines) and '{' in lines[i]:
                i += 1
            new_lines.append(' ' * (indent + 4) + '# PATCHED: Protocol version validation disabled - always allow')
            new_lines.append(' ' * (indent + 4) + 'return True')
            while i < len(lines):
                current_line = lines[i]
                if not current_line.strip():
                    i += 1
                    continue
                current_indent = len(current_line) - len(current_line.lstrip())
                if (current_indent <= indent and 
                    (current_line.strip().startswith('def ') or 
                     current_line.strip().startswith('async def ') or 
                     current_line.strip().startswith('class '))):
                    break
                i += 1
            patched_methods.add('_validate_protocol_version')
            changes_made.append("_validate_protocol_version method")
            continue
        
        new_lines.append(line)
        i += 1
    
    if new_lines != lines:
        content = '\n'.join(new_lines)
    
    # Patch 4: Replace error messages related to session ID (be careful with f-strings)
    # Only replace complete string literals, not parts of f-strings
    error_replacements = [
        (r'"No valid session ID provided"', '"PATCHED: Session validation disabled"'),
        (r"'No valid session ID provided'", "'PATCHED: Session validation disabled'"),
        # Don't replace f-string patterns - they're too complex and can break syntax
    ]
    
    for pattern, replacement in error_replacements:
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
            changes_made.append(f"Error message: {pattern[:30]}...")
    
    # Patch 5: Replace any raise statements that check for session_id
    # Look for patterns like: if not session_id: raise ...
    session_check_pattern = r'if\s+(not\s+)?session_id[^:]*:\s*raise'
    if re.search(session_check_pattern, content, re.IGNORECASE):
        content = re.sub(session_check_pattern, 'if False:  # PATCHED: Session check disabled\n        pass  # raise', content, flags=re.IGNORECASE)
        changes_made.append("Session ID check conditions")
    
    # If content changed, write it back
    if content != original_content:
        logger.info(f"Patching {streamable_http_file}")
        # Create backup
        backup_file = streamable_http_file.with_suffix('.py.backup')
        if not backup_file.exists():
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(original_content)
            logger.info(f"Created backup: {backup_file}")
        
        # Write patched content
        with open(streamable_http_file, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"✓ Successfully patched {streamable_http_file}")
        logger.info(f"Changes made: {', '.join(changes_made)}")
        return True
    else:
        if '# PATCHED:' in content:
            logger.info("File already contains patches. Verification passed.")
            return True
        logger.warning("No changes made - validation methods may not exist or have different structure")
        return False


def patch_streamable_http_simple(fastmcp_path: Path):
    """Simpler approach: Direct string replacement for common patterns."""
    streamable_http_file = fastmcp_path / "server" / "streamable_http.py"
    
    if not streamable_http_file.exists():
        logger.error(f"File not found: {streamable_http_file}")
        return False
    
    logger.info(f"Reading {streamable_http_file} for simple patching")
    
    with open(streamable_http_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    original_lines = lines.copy()
    modified = False
    changes = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Patch _validate_session method
        if 'async def _validate_session' in line or 'def _validate_session' in line:
            indent = len(line) - len(line.lstrip())
            # Find the method body and replace it
            i += 1
            # Skip until we find the return statement or end of method
            body_start = i
            while i < len(lines):
                current_line = lines[i]
                current_indent = len(current_line) - len(current_line.lstrip()) if current_line.strip() else indent + 4
                
                # Check if we've reached the next method/class
                if (current_line.strip().startswith('def ') or 
                    current_line.strip().startswith('async def ') or 
                    current_line.strip().startswith('class ')) and current_indent <= indent:
                    break
                
                # Check if we've reached a return statement (end of method logic)
                if 'return' in current_line and current_indent > indent:
                    # Replace everything from body_start to i (inclusive) with simple return True
                    lines[body_start:i+1] = [
                        ' ' * (indent + 4) + '# PATCHED: Session validation disabled\n',
                        ' ' * (indent + 4) + 'return True\n'
                    ]
                    modified = True
                    changes.append("_validate_session method body")
                    break
                
                i += 1
            continue
        
        # Patch _validate_request_headers method
        if 'async def _validate_request_headers' in line or 'def _validate_request_headers' in line:
            indent = len(line) - len(line.lstrip())
            i += 1
            body_start = i
            while i < len(lines):
                current_line = lines[i]
                current_indent = len(current_line) - len(current_line.lstrip()) if current_line.strip() else indent + 4
                
                if (current_line.strip().startswith('def ') or 
                    current_line.strip().startswith('async def ') or 
                    current_line.strip().startswith('class ')) and current_indent <= indent:
                    break
                
                if 'return' in current_line and current_indent > indent:
                    lines[body_start:i+1] = [
                        ' ' * (indent + 4) + '# PATCHED: Request headers validation disabled\n',
                        ' ' * (indent + 4) + 'return True\n'
                    ]
                    modified = True
                    changes.append("_validate_request_headers method body")
                    break
                
                i += 1
            continue
        
        # Replace error messages
        if 'No valid session ID' in line:
            lines[i] = line.replace('No valid session ID', 'PATCHED: Session validation disabled')
            modified = True
            changes.append("Error message")
        
        i += 1
    
    if modified:
        # Create backup
        backup_file = streamable_http_file.with_suffix('.py.backup')
        if not backup_file.exists():
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.writelines(original_lines)
            logger.info(f"Created backup: {backup_file}")
        
        # Write patched content
        with open(streamable_http_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        logger.info(f"✓ Successfully patched {streamable_http_file}")
        logger.info(f"Changes made: {', '.join(changes)}")
        return True
    else:
        # Check if already patched
        content = ''.join(lines)
        if '# PATCHED:' in content:
            logger.info("File already contains patches. Verification passed.")
            return True
        logger.warning("No changes made")
        return False


def main():
    """Main function to patch FastMCP."""
    logger.info("=" * 80)
    logger.info("FastMCP Session Validation Disabler")
    logger.info("=" * 80)
    
    fastmcp_path = find_fastmcp_installation()
    if not fastmcp_path:
        logger.error("Failed to find FastMCP installation")
        sys.exit(1)
    
    # Try regex-based patching first (more reliable)
    logger.info("Attempting regex-based patching...")
    success = patch_streamable_http(fastmcp_path)
    
    if not success:
        logger.info("Regex patching didn't make changes, trying simple line-by-line patching...")
        success = patch_streamable_http_simple(fastmcp_path)
    
    if success:
        # Verify the patch was applied
        logger.info("Verifying patch was applied...")
        streamable_http_file = fastmcp_path / "server" / "streamable_http.py"
        if streamable_http_file.exists():
            with open(streamable_http_file, 'r', encoding='utf-8') as f:
                content = f.read()
            if '# PATCHED:' in content and 'return True' in content:
                logger.info("✓ Verification passed: Patch markers found in file")
            else:
                logger.warning("⚠ Verification warning: Patch markers not clearly visible")
        
        logger.info("=" * 80)
        logger.info("✓ FastMCP patching completed successfully!")
        logger.info("Session validation has been permanently disabled.")
        logger.info("=" * 80)
        sys.exit(0)
    else:
        logger.error("=" * 80)
        logger.error("✗ FastMCP patching failed!")
        logger.error("The file structure may have changed. Please check manually.")
        logger.error("=" * 80)
        # Don't exit with error - allow build to continue
        # The runtime patches in main.py will still work as fallback
        logger.warning("Continuing build - runtime patches in main.py will be used as fallback")
        sys.exit(0)


if __name__ == "__main__":
    main()

