"""Starts a simple application development server."""
# Third-party modules
import uweb

# Application
import base

def main():
  app = base.main()
  app.serve()


if __name__ == '__main__':
  main()
